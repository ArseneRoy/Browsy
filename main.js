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

// Max for Live device — Browsy Connect
const M4L_SRC  = path.join(__dirname, 'Browsy_connect.amxd')
const M4L_DEST = path.join(
  require('os').homedir(),
  'Music', 'Ableton', 'User Library', 'Presets', 'Audio Effects', 'Max Audio Effect', 'Browsy Connect.amxd'
)

ipcMain.handle('m4l:check', () => fs.existsSync(M4L_DEST))

ipcMain.handle('m4l:install', () => {
  try {
    fs.mkdirSync(path.dirname(M4L_DEST), { recursive: true })
    fs.copyFileSync(M4L_SRC, M4L_DEST)
    return { ok: true, dest: M4L_DEST }
  } catch (err) {
    return { ok: false, error: err.message }
  }
})

// Hammerspoon integration
const HS_INIT   = path.join(require('os').homedir(), '.hammerspoon', 'init.lua')
const HS_MARKER = '-- Browsy:'
const HS_SNIPPET = `
-- Browsy: open/focus when @ is pressed in Ableton Live
local function _browsy_openOrFocus()
  local app = hs.application.find('Browsy')
  if app then app:activate()
  else hs.application.open('/Applications/Browsy.app') end
end
local _browsy_watcher = hs.eventtap.new({hs.eventtap.event.types.keyDown}, function(e)
  local front = hs.application.frontmostApplication()
  if not front or front:name() ~= 'Live' then return false end
  if e:getCharacters(true) == '@' then _browsy_openOrFocus(); return true end
  return false
end)
_browsy_watcher:start()
`

ipcMain.handle('hammerspoon:check', () => {
  if (!fs.existsSync(HS_INIT)) return 'missing'
  const content = fs.readFileSync(HS_INIT, 'utf-8')
  return content.includes(HS_MARKER) ? 'installed' : 'not-configured'
})

ipcMain.handle('hammerspoon:install', () => {
  try {
    fs.mkdirSync(path.dirname(HS_INIT), { recursive: true })
    const existing = fs.existsSync(HS_INIT) ? fs.readFileSync(HS_INIT, 'utf-8') : ''
    if (existing.includes(HS_MARKER)) return { ok: true, already: true }
    fs.writeFileSync(HS_INIT, existing + HS_SNIPPET)
    return { ok: true, already: false }
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

app.whenReady().then(() => {
  setupOSC()
  createWindow()
})

app.on('window-all-closed', () => {
  try { oscServer?.close() } catch (_) {}
  try { oscClient?.close() } catch (_) {}
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
