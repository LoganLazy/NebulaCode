const { app, BrowserWindow } = require("electron")
const { spawn } = require("child_process")
const path = require("path")
const fs = require("fs")
const http = require("http")

app.disableHardwareAcceleration()  // 排除显卡渲染导致的黑屏

let LOG = null
function dlog(msg) {
  try {
    fs.appendFileSync(LOG || "aidek-debug.log",
      `[${new Date().toISOString()}] ${msg}\n`)
  } catch (e) {}
}

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
    res.resume(); dlog("✓ 后端服务就绪"); cb(true)
  })
  req.on("error", () => {
    if (tries-- <= 0) { dlog("❌ 等待超时, 后端始终未就绪"); cb() }
    else setTimeout(() => waitServer(cb, tries), 800)
  })
  req.setTimeout(1500, () => req.destroy())
}

const ERROR_PAGE = "data:text/html;charset=utf-8," + encodeURIComponent(
  '<body style="background:#0d1017;color:#e4e8f0;font-family:sans-serif;'
  + 'display:flex;align-items:center;justify-content:center;height:100vh;margin:0">'
  + '<div style="text-align:center"><h2>⚠️ 页面加载失败</h2>'
  + '<p style="color:#8b93a5">正在自动重试…若持续失败请把 aidek-debug.log 发给开发者</p></div></body>')


function createWindow(backendOk) {
  dlog("创建窗口, backendOk=" + backendOk)
  win = new BrowserWindow({
    width: 1400, height: 900,
    title: "NebulaCode",
    autoHideMenuBar: true,
    backgroundColor: "#0d1017",
    show: false,
    webPreferences: { contextIsolation: true },
  })

  // 内容真正就绪后才显示窗口 —— 杜绝黑屏窗口
  win.once("ready-to-show", () => {
    dlog("✓ 页面ready-to-show, 显示窗口")
    win.show()
  })

  let retries = 0
  const loadApp = () => {
    dlog(`加载应用界面(第${retries + 1}次尝试)`)
    win.loadURL(`http://127.0.0.1:${PORT}`).catch((e) => {
      dlog("loadURL异常: " + e.message)
    })
  }

  win.webContents.on("did-fail-load", (e, code, desc, url, isMain) => {
    if (!isMain) return
    dlog(`did-fail-load code=${code} desc=${desc}`)
    if (retries < 5) {
      retries++
      setTimeout(loadApp, 1500 * retries)
    } else {
      win.loadURL(ERROR_PAGE)
    }
  })
  win.webContents.on("did-finish-load", () => dlog("✓ 页面加载完成"))

  if (backendOk) {
    loadApp()
  } else {
    win.loadURL(ERROR_PAGE)
  }
  win.on("closed", () => (win = null))
}

app.whenReady().then(() => {
  try {
    LOG = path.join(homeDir(), "aidek-debug.log")
  } catch (e) {}
})
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
