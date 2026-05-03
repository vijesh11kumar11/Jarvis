/* electron/preload.js
 * Bridges the renderer (React) and the main process for window control,
 * native operations, and the Python backend.
 */
const { contextBridge, ipcRenderer } = require("electron");

const invoke = (ch, ...args) => ipcRenderer.invoke(ch, ...args);
const on = (ch, fn) => {
  const wrapped = (_e, ...args) => fn(...args);
  ipcRenderer.on(ch, wrapped);
  return () => ipcRenderer.removeListener(ch, wrapped);
};

contextBridge.exposeInMainWorld("jarvis", {
  // Window control
  windowControl: (cmd) => invoke("window-control", cmd),

  // System
  getSystemInfo: () => invoke("system-info"),

  // Backend wrappers
  chat: (payload) => invoke("chat", payload),
  speak: (text, voiceId) => invoke("speak", { text, voice_id: voiceId }),
  research: (payload) => invoke("research", payload),
  executeComputer: (payload) => invoke("execute-computer", payload),
  analyzeDocument: (fileBuffer, filename, userId) =>
    invoke("analyze-document", { fileBuffer, filename, userId }),
  analyzeGithub: (url, userId) => invoke("analyze-github", { url, userId }),
  generateIdeas: (payload) => invoke("generate-ideas", payload),
  evaluateIdea: (payload) => invoke("evaluate-idea", payload),
  getNews: (kind, userId, query) => invoke("get-news", { kind, userId, query }),
  saveDailyContext: (payload) => invoke("save-daily-context", payload),

  // Events
  onWakeWord: (fn) => on("wake-word", fn),
  onPythonReady: (fn) => on("python-ready", fn),
  onPythonLog: (fn) => on("python-log", fn),
  removeListener: (ch, fn) => ipcRenderer.removeListener(ch, fn),
});
