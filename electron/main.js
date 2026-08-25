const { app, BrowserWindow } = require("electron")
const { spawn } = require("child_process")
const path = require("path")
const http = require("http")

const PORT = 8790
let backendProc = null
let win = null

function homeDir() {
  try {
    const dir = path.dirname(app.getPath("exe"))
    require("fs").accessSync(dir, require("fs").constants.W_OK)
    return dir
  } catch (e) {
    return app.getPath("userData")
  }
}

function startBackend() {
  const res = process.resourcesPath || path.join(__dirname, "resources")
  const candidates = [
    path.join(res, "backend", "AIDesk-backend", "AIDesk-backend.exe"),
    path.join(__dirname, "..", "server", "AIDesk-backend.exe"),
  ]
  const exe = candidates.find((p) => {
    try { return require("fs").existsSync(p) } catch (e) { return false }
  })
  if (!exe) {
    console.log("[AIDesk] 未找到后端引擎, 若已手动启动可直接使用")
    return
  }
  const home = homeDir()
  backendProc = spawn(exe, [], {
    cwd: home,
    env: { ...process.env, AI_DESK_HOME: home },
    stdio: "ignore",
    windowsHide: true,
  })
}

function waitServer(cb, tries = 60) {
  const req = http.get(`http://127.0.0.1:${PORT}/api/sys/poll`, (res) => {
    res.resume(); cb()
  })
  req.on("error", () => {
    if (tries-- <= 0) return cb()
    setTimeout(() => waitServer(cb, tries), 800)
  })
  req.setTimeout(1500, () => req.destroy())
}

function createWindow() {
  win = new BrowserWindow({
    width: 1400, height: 900,
    title: "AI Desk",
    autoHideMenuBar: true,
    backgroundColor: "#0d1017",
    webPreferences: { contextIsolation: true },
  })
  win.loadURL(`http://127.0.0.1:${PORT}`)
  win.on("closed", () => (win = null))
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) app.quit()
else {
  app.on("second-instance", () => {
    if (win) { if (win.isMinimized()) win.restore(); win.focus() }
  })
  app.whenReady().then(() => { startBackend(); waitServer(createWindow) })
  app.on("window-all-closed", () => {
    if (backendProc) { try { backendProc.kill() } catch (e) {} }
    app.quit()
  })
}
