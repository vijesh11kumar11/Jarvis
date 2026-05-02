# 🤖 Marketing Jarvis

An Iron Man–style desktop AI assistant with a 15-year marketing strategist brain. Voice-controlled. Remembers conversations. Analyses your market live. Built on **Gemini + Groq** (no Claude, no OpenAI). Runs locally.

---

## ⚡ Setup (about 10 minutes)

### 1. Get API keys

| Key | Where | Cost |
|-----|-------|------|
| **Gemini** (required) | https://makersuite.google.com/app/apikey | Free |
| **Groq** (required) | https://console.groq.com/keys | Free |
| ElevenLabs (optional, voice) | https://elevenlabs.io | Free 10k chars/mo |
| Tavily (optional, market research) | https://app.tavily.com | Free 1000 searches/mo |
| Porcupine (optional, wake word "Jarvis") | https://console.picovoice.ai | Free personal |

> Without ElevenLabs the app falls back to your local `pyttsx3` voice.
> Without Tavily, market research is disabled but everything else works.
> Without Porcupine, wake-word is disabled — use double clap or `Ctrl+Space`.

### 2. Install
```bash
python setup.py
```
This will:
- check Python ≥ 3.10
- install `requirements.txt`
- run `npm install`
- create `backend/.env` from the example
- initialise the SQLite DB
- ping Gemini + Groq if keys are set

### 3. Add your keys
Edit `backend/.env` and paste your real keys.
Your Gemini and Groq keys are already filled in (you provided them).

### 4. Launch
- **Windows**: double-click `start.bat`
- **macOS/Linux**: `./start.sh`

The Python backend boots on `http://127.0.0.1:8000` and the Electron HUD opens automatically.

---

## 🎙 Wake options
- Press **Ctrl + Space**
- Click the orb / mic button
- Say **"Jarvis"** (only if Porcupine key is set)
- **Double-clap** (uses your microphone)

## 🗣 Try saying
```
"Analyse the market for handmade leather wallets in Chennai"
"Write three Facebook ad hooks for premium yoga mats"
"Open YouTube"
"Take a screenshot and tell me what you see"
"Send WhatsApp to mom: I'll be home by 9"
"What's my budget recommendation for launching in Mumbai?"
```

## 🧠 What's inside

```
backend/                  Python FastAPI backend
  main.py                 REST + SSE endpoints
  brain/
    ai_router.py          Gemini + Groq routing with fallback
    marketing_brain.py    15-yr CMO system prompt
    computer_control.py   Open apps/sites, WhatsApp, screenshots
  services/
    voice_pipeline.py     faster-whisper + ElevenLabs + clap detect
    research.py           Tavily searches + Gemini synthesis
  db/
    database.py           aiosqlite schema and CRUD
    memory.py             Long-term memory + summaries

electron/                 Electron main + preload
src/                      React + Tailwind + framer-motion HUD
  components/Orb.jsx      The animated Iron-Man orb
  pages/JarvisChat.jsx    Main HUD screen
  components/Onboarding   7-step cinematic onboarding
```

## 🔁 Routing rules
- **Strategy / copy / analysis** → Gemini 2.0 Flash
- **Quick voice replies / intent parsing** → Groq llama-3.3-70b
- **Vision / screenshot understanding** → Gemini 1.5 Pro
- If primary fails → automatically falls back to the other

## 🗃 Local data
Everything is in `jarvis.db` (SQLite) at the project root. Delete it to reset.

## 🧯 Troubleshooting
- **Backend won't start** → `python backend/main.py` to see the trace
- **No audio** → unset `ELEVENLABS_API_KEY` to use the local voice
- **Mic permission** → allow microphone access in your OS settings
- **Wake word not detected** → set `PORCUPINE_ACCESS_KEY` in `.env`

## ⚠ Security
Your API keys live in `backend/.env`. Don't commit that file. **Rotate any key you've ever pasted publicly.**
