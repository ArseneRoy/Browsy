const { contextBridge, ipcRenderer } = require('electron')

// Single shared dispatcher — one ipcRenderer listener, routes to registered callbacks
const oscListeners = {}
ipcRenderer.on('osc:message', (event, msg) => {
  const cbs = oscListeners[msg.address]
  if (cbs) cbs.forEach(cb => cb(...msg.args))
})

// OSC bridge — exposed as window.osc in the renderer
contextBridge.exposeInMainWorld('osc', {
  // Send an OSC message to M4L
  send: (address, ...args) => {
    ipcRenderer.send('osc:send', address, args)
  },

  // Subscribe to incoming OSC messages by address
  on: (address, callback) => {
    if (!oscListeners[address]) oscListeners[address] = []
    oscListeners[address].push(callback)
  },
})

// Config file bridge — exposed as window.electronConfig
contextBridge.exposeInMainWorld('electronConfig', {
  read:       ()       => ipcRenderer.invoke('config:read'),
  write:      (data)   => ipcRenderer.invoke('config:write', data),
  pickFolder: ()       => ipcRenderer.invoke('config:pick-folder'),
  path:       ()       => ipcRenderer.invoke('config:path'),
})

// Remote script installer + Hammerspoon integration
contextBridge.exposeInMainWorld('electronInstall', {
  check:               () => ipcRenderer.invoke('remote-script:check'),
  installRemoteScript: () => ipcRenderer.invoke('remote-script:install'),
  checkHammerspoon:    () => ipcRenderer.invoke('hammerspoon:check'),
  installHammerspoon:  () => ipcRenderer.invoke('hammerspoon:install'),
  checkM4L:            () => ipcRenderer.invoke('m4l:check'),
  installM4L:          () => ipcRenderer.invoke('m4l:install'),
})

// Window controls — exposed as window.electronWindow
contextBridge.exposeInMainWorld('electronWindow', {
  close:        () => ipcRenderer.send('window:close'),
  minimize:     () => ipcRenderer.send('window:minimize'),
  focusAbleton: () => ipcRenderer.send('window:focusAbleton'),
})
