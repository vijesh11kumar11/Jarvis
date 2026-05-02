const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('jarvis', {
  chat: (data) => ipcRenderer.invoke('chat', data),
  research: (data) => ipcRenderer.invoke('research', data),
  executeComputer: (action) => ipcRenderer.invoke('computer-action', action),
  getSystemInfo: () => ipcRenderer.invoke('system-info'),
  windowControl: (action) => ipcRenderer.invoke('window-control', action),
  onWakeWord: (cb) => ipcRenderer.on('wake-word-detected', (_e, data) => cb(data)),
  onPythonReady: (cb) => ipcRenderer.on('python-ready', (_e, data) => cb(data)),
  onPythonLog: (cb) => ipcRenderer.on('python-log', (_e, data) => cb(data)),
})
