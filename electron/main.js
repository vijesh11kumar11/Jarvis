// electron/main.js — Electron main process
const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, nativeImage } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')

const isDev = !app.isPackaged
let mainWindow = null
let tray = null
let pyProc = null

function startBackend() {
  if (pyProc) return
  const cwd = path.join(__dirname, '..')
  const pythonExe = process.platform === 'win32' ? 'python' : 'python3'
  pyProc = spawn(pythonExe, ['backend/main.py'], { cwd, env: process.env })
  pyProc.stdout.on('data', d => {
    const msg = d.toString()
    process.stdout.write('[py] ' + msg)
    if (mainWindow) mainWindow.webContents.send('python-log', msg)
  })
  pyProc.stderr.on('data', d => {
    const msg = d.toString()
    process.stderr.write('[py-err] ' + msg)
    if (mainWindow) mainWindow.webContents.send('python-log', msg)
  })
  pyProc.on('close', code => {
    console.log('[py] exited with code', code)
    pyProc = null
  })
  // Poll backend until ready, then notify renderer
  const start = Date.now()
  const check = () => {
    http.get('http://127.0.0.1:8000/health', r => {
      if (r.statusCode === 200) {
        if (mainWindow) mainWindow.webContents.send('python-ready', true)
        return
      }
      if (Date.now() - start < 30000) setTimeout(check, 500)
    }).on('error', () => {
      if (Date.now() - start < 30000) setTimeout(check, 500)
    })
  }
  setTimeout(check, 800)
}

function stopBackend() {
  if (pyProc) {
    try { pyProc.kill() } catch (e) {}
    pyProc = null
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    frame: false,
    backgroundColor: '#000000',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
  mainWindow.once('ready-to-show', () => mainWindow.show())

  mainWindow.on('close', e => {
    if (!app.isQuitting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })
}

function createTray() {
  const iconPath = path.join(__dirname, 'icon.png')
  let img
  try { img = nativeImage.createFromPath(iconPath) } catch { img = nativeImage.createEmpty() }
  if (img.isEmpty()) img = nativeImage.createEmpty()
  tray = new Tray(img)
  tray.setToolTip('Marketing Jarvis')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show Jarvis', click: () => { if (mainWindow) mainWindow.show() } },
    { label: 'Hide', click: () => { if (mainWindow) mainWindow.hide() } },
    { type: 'separator' },
    { label: 'Quit', click: () => { app.isQuitting = true; app.quit() } },
  ]))
  tray.on('click', () => mainWindow && (mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show()))
}

// IPC bridge
function fetchJson(url, opts) {
  return new Promise((resolve, reject) => {
    const u = new URL(url)
    const lib = u.protocol === 'https:' ? require('https') : http
    const data = opts && opts.body ? opts.body : null
    const req = lib.request({
      hostname: u.hostname, port: u.port, path: u.pathname + u.search,
      method: opts && opts.method || 'GET',
      headers: { 'Content-Type': 'application/json', ...(opts && opts.headers || {}) },
    }, r => {
      let buf = ''
      r.on('data', c => buf += c)
      r.on('end', () => {
        try { resolve(JSON.parse(buf)) } catch { resolve(buf) }
      })
    })
    req.on('error', reject)
    if (data) req.write(data)
    req.end()
  })
}

ipcMain.handle('chat', async (_e, payload) => fetchJson('http://127.0.0.1:8000/chat', {
  method: 'POST', body: JSON.stringify(payload),
}))
ipcMain.handle('research', async (_e, payload) => fetchJson('http://127.0.0.1:8000/research', {
  method: 'POST', body: JSON.stringify(payload),
}))
ipcMain.handle('computer-action', async (_e, payload) => fetchJson('http://127.0.0.1:8000/computer/execute', {
  method: 'POST', body: JSON.stringify(payload),
}))
ipcMain.handle('system-info', async () => fetchJson('http://127.0.0.1:8000/system/info'))
ipcMain.handle('window-control', async (_e, action) => {
  if (!mainWindow) return
  if (action === 'minimize') mainWindow.minimize()
  if (action === 'close') mainWindow.hide()
  if (action === 'maximize') {
    if (mainWindow.isMaximized()) mainWindow.unmaximize()
    else mainWindow.maximize()
  }
})

app.whenReady().then(() => {
  startBackend()
  createWindow()
  createTray()
  globalShortcut.register('Control+Space', () => {
    if (!mainWindow) return
    if (mainWindow.isVisible()) mainWindow.focus()
    else mainWindow.show()
    mainWindow.webContents.send('wake-word-detected', { source: 'hotkey' })
  })
})

app.on('window-all-closed', e => { e.preventDefault() })
app.on('before-quit', () => { app.isQuitting = true; stopBackend() })
app.on('will-quit', () => { globalShortcut.unregisterAll() })
