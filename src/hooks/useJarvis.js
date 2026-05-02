// src/hooks/useJarvisApi.js — fetch helpers (works in Electron OR plain browser)
import { API_BASE } from '../config'

export async function chatStream({ payload, onDelta, onDone, onError }) {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.body) throw new Error('No stream')
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        try {
          const obj = JSON.parse(line.slice(5).trim())
          if (obj.delta) onDelta?.(obj.delta)
          if (obj.done)  onDone?.(obj)
          if (obj.error) onError?.(obj.error)
        } catch {}
      }
    }
    onDone?.({})
  } catch (e) {
    onError?.(e.message)
  }
}

export async function speakText(text, voiceId) {
  const res = await fetch(`${API_BASE}/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice_id: voiceId }),
  })
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  await audio.play().catch(() => {})
  return audio
}

export async function transcribeBlob(blob) {
  const fd = new FormData()
  fd.append('audio', blob, 'speech.webm')
  const res = await fetch(`${API_BASE}/listen`, { method: 'POST', body: fd })
  return res.json()
}

export async function research(payload) {
  const res = await fetch(`${API_BASE}/research`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function executeComputer(payload) {
  const res = await fetch(`${API_BASE}/computer/execute`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function systemInfo() {
  const res = await fetch(`${API_BASE}/system/info`)
  return res.json()
}

export async function health() {
  try {
    const r = await fetch(`${API_BASE}/health`)
    return r.json()
  } catch { return { ok: false } }
}

export async function uploadDocument(file, userId = 'anonymous') {
  const fd = new FormData()
  fd.append('file', file, file.name)
  const url = `${API_BASE}/upload/document?user_id=${encodeURIComponent(userId)}`
  const r = await fetch(url, { method: 'POST', body: fd })
  return r.json()
}

export async function analyzeGithub(payload) {
  const r = await fetch(`${API_BASE}/analyze/github`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return r.json()
}

export async function visionChat(payload) {
  const r = await fetch(`${API_BASE}/vision/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return r.json()
}

export async function getAboutMe(userId) {
  const r = await fetch(`${API_BASE}/about-me/${encodeURIComponent(userId)}`)
  return r.json()
}

export async function saveAboutMe(payload) {
  const r = await fetch(`${API_BASE}/about-me`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return r.json()
}

export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const s = reader.result || ''
      const b64 = String(s).split(',')[1] || String(s)
      resolve(b64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
