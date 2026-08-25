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
    path.join(res, "backend", "NebulaCode-backend.exe"),
    path.join(res, "backend", "NebulaCode-backend", "NebulaCode-backend.exe"),
    path.join(__dirname, "..", "server", "NebulaCode-backend.exe"),
  ]
  const exe = candidates.find((p) => {
    try { return require("fs").existsSync(p) } catch (e) { return false }
  })
  if (!exe) {
    console.log("[NebulaCode] 未找到后端引擎, 若已手动启动可直接使用")
    return
  }
  const home = homeDir()
  backendProc = spawn(exe, [], {
    cwd: home,
    env: { ...process.env, NEBULACODE_HOME: home },
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

function createWindow(backendOk) {
  win = new BrowserWindow({
    width: 1400, height: 900,
    title: "NebulaCode",
    autoHideMenuBar: true,
    backgroundColor: "#0d1017",
    webPreferences: { contextIsolation: true },
  })
  if (backendOk) {
    win.loadURL(`http://127.0.0.1:${PORT}`)
  } else {
    win.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(
      '<body style="background:#0d1017;color:#e4e8f0;font-family:sans-serif;'
      + 'display:flex;align-items:center;justify-content:center;height:100vh;margin:0">'
      + '<div style="text-align:center"><h2>⚠️ 后端引擎启动失败</h2>'
      + '<p style="color:#8b93a5">请确认解压完整(resources/backend 文件夹存在)<br>'
      + '并尝试关闭杀毒软件后重新解压</p></div></body>'))
  }
  win.on("closed", () => (win = null))
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) app.quit()
else {
  app.on("second-instance", () => {
    if (win) { if (win.isMinimized()) win.restore(); win.focus() }
  })
  app.whenReady().then(() => { startBackend(); waitServer((ok) => createWindow(ok)) })
  app.on("window-all-closed", () => {
    if (backendProc) { try { backendProc.kill() } catch (e) {} }
    app.quit()
  })
}
