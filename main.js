const { app, BrowserWindow, ipcMain, globalShortcut, dialog } = require('electron')
const { exec } = require('child_process')
const fs = require('fs')
const path = require('path')

// Shared config file — readable by both Electron and browser.py
const CONFIG_PATH = path.join(app.getPath('userData'), 'vst_browser_config.json')
const { Client, Server } = require('node-osc')

let mainWindow
let oscClient
let oscServer

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 520,
    height: 720,
    minWidth: 420,
    minHeight: 500,
    frame: false,
    alwaysOnTop: false,
    backgroundColor: '#141414',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.loadFile('browsy.html')
  mainWindow.on('closed', () => { mainWindow = null })
}

function setupOSC() {
  // Client: send to M4L on port 11000
  oscClient = new Client('127.0.0.1', 11000)

  // Server: receive from M4L on port 11001
  try {
    oscServer = new Server(11001, '0.0.0.0', () => {
      console.log('[OSC] Server listening on port 11001')
    })

    oscServer.on('message', (msg) => {
      const [address, ...args] = msg
      console.log('[OSC IN]', address, args)
      if (address === '/browsy/focus' && mainWindow) {
        mainWindow.show()
        mainWindow.focus()
        return
      }
      if (mainWindow) {
        mainWindow.webContents.send('osc:message', { address, args })
      }
    })

    oscServer.on('error', (err) => {
      console.error('[OSC] Server error:', err)
    })
  } catch (err) {
    console.error('[OSC] Failed to start server:', err)
  }
}

// Renderer → OSC out
ipcMain.on('osc:send', (event, address, args) => {
  console.log('[OSC OUT]', address, args)
  try {
    oscClient.send(address, ...args, (err) => {
      if (err) console.error('[OSC] Send error:', err)
    })
  } catch (err) {
    console.error('[OSC] Send error:', err)
  }
})

// Config file read/write
ipcMain.handle('config:read', () => {
  try { return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8')) } catch { return {} }
})
ipcMain.handle('config:write', (event, data) => {
  fs.mkdirSync(path.dirname(CONFIG_PATH), { recursive: true })
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2))
})
ipcMain.handle('config:pick-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] })
  return result.canceled ? null : result.filePaths[0]
})
ipcMain.handle('config:path', () => CONFIG_PATH)

// Check / Install Ableton Remote Script
ipcMain.handle('remote-script:check', () => {
  const dest = path.join(
    require('os').homedir(),
    'Music', 'Ableton', 'User Library', 'Remote Scripts', 'Browsy'
  )
  const required = ['__init__.py', 'Browsy.py', 'browser.py', 'osc_server.py']
  return required.every(f => fs.existsSync(path.join(dest, f)))
})

ipcMain.handle('remote-script:install', () => {
  const src = path.join(__dirname, 'remote-script', 'Browsy')
  const dest = path.join(
    require('os').homedir(),
    'Music', 'Ableton', 'User Library', 'Remote Scripts', 'Browsy'
  )
  try {
    fs.mkdirSync(dest, { recursive: true })
    for (const file of fs.readdirSync(src).filter(f => f.endsWith('.py'))) {
      fs.copyFileSync(path.join(src, file), path.join(dest, file))
    }
    return { ok: true, dest }
  } catch (err) {
    return { ok: false, error: err.message }
  }
})



// Window controls
ipcMain.on('window:close',    () => mainWindow?.close())
ipcMain.on('window:minimize', () => mainWindow?.minimize())
ipcMain.on('window:focusAbleton', () => {
  exec(`osascript -e 'tell application "Live" to activate'`)
})

// ─── Global shortcuts (active when Ableton is frontmost) ──────────────────────
const SHORTCUT_KEYS = ['1','2','3','4','5','6']
let focusPollInterval = null

function getFrontApp() {
  return new Promise(resolve => {
    exec(`osascript -e 'tell application "System Events" to get name of first application process whose frontmost is true'`, (err, stdout) => {
      resolve(err ? '' : stdout.trim())
    })
  })
}

function registerGlobalShortcuts() {
  SHORTCUT_KEYS.forEach((key, i) => {
    if (globalShortcut.isRegistered(key)) return
    globalShortcut.register(key, () => {
      mainWindow?.webContents.send('shortcut:trigger', i)
    })
  })
  if (!globalShortcut.isRegistered('Cmd+Shift+F')) {
    globalShortcut.register('Cmd+Shift+F', () => {
      if (mainWindow) { mainWindow.show(); mainWindow.focus() }
    })
  }
}

function unregisterGlobalShortcuts() {
  SHORTCUT_KEYS.forEach(key => globalShortcut.unregister(key))
  globalShortcut.unregister('Cmd+Shift+F')
}

function setupFocusWatcher(win) {
  win.on('focus', () => {
    clearInterval(focusPollInterval)
    focusPollInterval = null
    unregisterGlobalShortcuts()
  })

  win.on('blur', () => {
    focusPollInterval = setInterval(async () => {
      const front = await getFrontApp()
      if (front === 'Live') {
        registerGlobalShortcuts()
      } else {
        unregisterGlobalShortcuts()
      }
    }, 200)
  })
}

app.whenReady().then(() => {
  setupOSC()
  createWindow()
  setupFocusWatcher(mainWindow)
})

app.on('window-all-closed', () => {
  try { oscServer?.close() } catch (_) {}
  try { oscClient?.close() } catch (_) {}
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
