/* electron/main.js
 * Frameless Electron shell with embedded Python backend.
 * Forwards renderer IPC calls to the FastAPI backend on :8000.
 */
const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");
const fetch = (...a) => import("node-fetch").then(({ default: f }) => f(...a));
const FormData = require("form-data");

const isDev = !app.isPackaged;
const BACKEND_URL = "http://localhost:8000";
let mainWindow = null;
let pyProcess = null;
let backendReady = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    frame: false,
    backgroundColor: "#04060d",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }

  mainWindow.webContents.on("did-finish-load", () => {
    if (backendReady) mainWindow.webContents.send("python-ready", true);
  });
}

// ─────── Python backend lifecycle ───────
function pickPython() {
  // Prefer system python on Windows; fall back to "python3" elsewhere.
  if (process.platform === "win32") return "python";
  return "python3";
}

async function pingBackend() {
  try {
    const r = await fetch(`${BACKEND_URL}/health`);
    return r.ok;
  } catch { return false; }
}

async function startPython() {
  // If a backend is already running, skip spawning.
  if (await pingBackend()) {
    backendReady = true;
    if (mainWindow) mainWindow.webContents.send("python-ready", true);
    return;
  }

  const py = pickPython();
  const root = path.resolve(__dirname, "..");
  const entry = path.join(root, "backend", "main.py");
  if (!fs.existsSync(entry)) {
    console.error("[electron] backend/main.py not found");
    return;
  }
  pyProcess = spawn(py, [entry], { cwd: root, env: process.env });

  pyProcess.stdout.on("data", (d) => {
    const txt = d.toString();
    process.stdout.write(`[py] ${txt}`);
    if (mainWindow) mainWindow.webContents.send("python-log", txt);
    if (!backendReady && /listening on http/.test(txt)) {
      backendReady = true;
      mainWindow?.webContents.send("python-ready", true);
    }
  });
  pyProcess.stderr.on("data", (d) => {
    const txt = d.toString();
    process.stderr.write(`[py-err] ${txt}`);
    if (mainWindow) mainWindow.webContents.send("python-log", txt);
  });
  pyProcess.on("exit", (c) => console.log(`[py] exited with code ${c}`));
}

// ─────── IPC handlers ───────
ipcMain.handle("window-control", async (_e, cmd) => {
  if (!mainWindow) return;
  if (cmd === "minimize") mainWindow.minimize();
  else if (cmd === "maximize")
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
  else if (cmd === "close") mainWindow.close();
});

ipcMain.handle("system-info", async () => {
  return { platform: process.platform, arch: process.arch,
           appVersion: app.getVersion(), backendReady };
});

async function postJson(path, body) {
  const r = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return await r.json();
}

ipcMain.handle("chat", async (_e, payload) => {
  // Buffer SSE → return final text (renderer can also call /chat directly for streaming)
  const r = await fetch(`${BACKEND_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await r.text();
  let full = "";
  for (const line of text.split(/\r?\n/)) {
    if (!line.startsWith("data:")) continue;
    try {
      const obj = JSON.parse(line.slice(5).trim());
      if (obj.delta) full += obj.delta;
    } catch {}
  }
  return { text: full };
});

ipcMain.handle("speak", async (_e, payload) => {
  const r = await fetch(`${BACKEND_URL}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const buf = Buffer.from(await r.arrayBuffer());
  return { base64: buf.toString("base64"), mime: "audio/mpeg" };
});

ipcMain.handle("research", (_e, p) => postJson("/research", p));
ipcMain.handle("execute-computer", (_e, p) => postJson("/computer/execute", p));
ipcMain.handle("generate-ideas", (_e, p) => postJson("/ideas/generate", p));
ipcMain.handle("evaluate-idea", (_e, p) => postJson("/ideas/evaluate", p));
ipcMain.handle("save-daily-context", (_e, p) => postJson("/daily-context", p));
ipcMain.handle("analyze-github", (_e, p) =>
  postJson("/analyze/github", { url: p.url, user_id: p.userId || "anonymous" }));

ipcMain.handle("analyze-document", async (_e, { fileBuffer, filename, userId }) => {
  const fd = new FormData();
  fd.append("file", Buffer.from(fileBuffer), { filename: filename || "doc" });
  fd.append("user_id", userId || "anonymous");
  const r = await fetch(`${BACKEND_URL}/analyze/document`, {
    method: "POST", body: fd, headers: fd.getHeaders(),
  });
  return await r.json();
});

ipcMain.handle("get-news", async (_e, { kind, userId, query }) => {
  if (kind === "morning") {
    const r = await fetch(`${BACKEND_URL}/news/morning-brief/${userId || "anonymous"}`);
    return await r.json();
  }
  if (kind === "market") {
    const r = await fetch(`${BACKEND_URL}/news/market-pulse`); return await r.json();
  }
  if (kind === "industry") {
    const r = await fetch(`${BACKEND_URL}/news/industry/${userId || "anonymous"}`);
    return await r.json();
  }
  if (kind === "search") return postJson("/news/search", { query, user_id: userId });
  const r = await fetch(`${BACKEND_URL}/news/today/${userId || "anonymous"}`);
  return await r.json();
});

// ─────── App lifecycle ───────
app.whenReady().then(async () => {
  createWindow();
  startPython();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (pyProcess) try { pyProcess.kill(); } catch {}
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (pyProcess) try { pyProcess.kill(); } catch {}
});
