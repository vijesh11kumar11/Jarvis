import React, { useEffect, useRef, useState } from 'react'
import Orb from '../components/Orb.jsx'
import HUDWidget from '../components/HUDWidget.jsx'
import TranscriptDisplay from '../components/TranscriptDisplay.jsx'
import UploadBar from '../components/UploadBar.jsx'
import { useJarvis } from '../context/JarvisContext.jsx'
import { useVoice } from '../hooks/useVoice.js'
import { chatStream, speakText, transcribeBlob, executeComputer, systemInfo } from '../hooks/useJarvis.js'
import { motion } from 'framer-motion'

export default function JarvisChat() {
  const { profile } = useJarvis()
  const [orbState, setOrbState] = useState('idle')
  const [messages, setMessages] = useState([])
  const [textInput, setTextInput] = useState('')
  const [showText, setShowText] = useState(false)
  const [sysInfo, setSys] = useState({})
  const { recording, amplitude, start, stop } = useVoice()
  const conversationIdRef = useRef(null)
  const audioRef = useRef(null)

  // System info polling
  useEffect(() => {
    const tick = async () => setSys(await systemInfo().catch(() => ({})))
    tick()
    const id = setInterval(tick, 5000)
    return () => clearInterval(id)
  }, [])

  // Wake word / hotkey listener via electron
  useEffect(() => {
    if (window.jarvis?.onWakeWord) {
      window.jarvis.onWakeWord(() => onMicClick())
    }
  }, [])

  // Startup greeting
  useEffect(() => {
    const greet = `Good day ${profile.userName}. ${profile.jarvisName} online. All systems nominal. How can I help you grow your business today?`
    setMessages([{ id: 'greet', role: 'assistant', content: greet }])
    setOrbState('speak')
    speakText(greet).then(a => {
      audioRef.current = a
      a.onended = () => setOrbState('idle')
    }).catch(() => setOrbState('idle'))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function sendMessage(text) {
    if (!text.trim()) return
    const userMsg = { id: Date.now(), role: 'user', content: text }
    setMessages(m => [...m, userMsg])

    // First check if it's a computer command
    setOrbState('think')
    try {
      const cmd = await executeComputer({
        natural_command: text, user_id: profile.userId || null,
      })
      if (cmd && cmd.success && cmd.action && cmd.action !== 'none') {
        const reply = cmd.speak || cmd.result || 'Done.'
        const asstMsg = { id: Date.now() + 1, role: 'assistant', content: reply }
        setMessages(m => [...m, asstMsg])
        setOrbState('speak')
        const audio = await speakText(reply).catch(() => null)
        if (audio) audio.onended = () => setOrbState('idle')
        else setOrbState('idle')
        return
      }
    } catch {}

    // Otherwise route to chat
    const asstId = Date.now() + 2
    setMessages(m => [...m, { id: asstId, role: 'assistant', content: '', streaming: true }])
    let full = ''

    await chatStream({
      payload: {
        user_id: profile.userId || 'local',
        jarvis_name: profile.jarvisName,
        user_name: profile.userName,
        message: text,
        business_context: {
          product: profile.product, target_audience: profile.audience,
          location: profile.location, budget_range: profile.budget,
          competitors: (profile.competitors || []).join(', '),
        },
        conversation_id: conversationIdRef.current,
      },
      onDelta: (d) => {
        full += d
        setMessages(m => m.map(x => x.id === asstId ? { ...x, content: full } : x))
      },
      onDone: (info) => {
        if (info.conversation_id) conversationIdRef.current = info.conversation_id
        setMessages(m => m.map(x => x.id === asstId ? { ...x, streaming: false } : x))
        setOrbState('speak')
        speakText(full).then(a => {
          audioRef.current = a
          a.onended = () => setOrbState('idle')
        }).catch(() => setOrbState('idle'))
      },
      onError: () => setOrbState('idle'),
    })
  }

  async function onMicClick() {
    if (!recording) {
      setOrbState('listen')
      await start()
    } else {
      const blob = await stop()
      setOrbState('think')
      try {
        const t = await transcribeBlob(blob)
        if (t.text) await sendMessage(t.text)
        else setOrbState('idle')
      } catch {
        setOrbState('idle')
      }
    }
  }

  return (
    <div className="relative w-full h-full overflow-hidden hex-grid">
      <div className="scan-line" />

      {/* Grid layout */}
      <div className="grid grid-cols-[260px_1fr_260px] grid-rows-[auto_1fr_auto] h-full p-6 gap-4">
        {/* Top-left clock */}
        <HUDWidget title="Local Time">
          <div className="font-display text-2xl text-violet-200">{sysInfo.time || '--:--'}</div>
          <div className="text-xs text-gray-500">{sysInfo.date || ''}</div>
          <div className="text-xs text-cyan-400/70 mt-1">{profile.location}</div>
        </HUDWidget>

        {/* Center top: orb */}
        <div className="flex items-start justify-center">
          <motion.div initial={{ opacity: 0, scale: 0.7 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 1.2, delay: 0.5 }}>
            <Orb state={orbState} name={profile.jarvisName} amplitude={amplitude} />
          </motion.div>
        </div>

        {/* Top-right system stats */}
        <HUDWidget title="System Status">
          <Row k="CPU" v={`${sysInfo.cpu_pct ?? '--'}%`} />
          <Row k="RAM" v={`${sysInfo.ram_pct ?? '--'}%`} />
          <Row k="BAT" v={`${sysInfo.battery_pct ?? '--'}%`} />
          <Row k="WIFI" v={sysInfo.wifi || '—'} />
        </HUDWidget>

        {/* Bottom-left market pulse */}
        <HUDWidget title="Market Pulse">
          <div className="text-emerald-400 text-xs">▲ Demand: scanning…</div>
          <div className="text-gray-400 text-xs mt-1">Last brief: today</div>
          <div className="text-violet-300 text-xs mt-1">{profile.product || '— add product in Settings —'}</div>
        </HUDWidget>

        {/* Center bottom transcript */}
        <div className="flex items-end justify-center pb-4">
          <TranscriptDisplay messages={messages} />
        </div>

        {/* Bottom-right memory */}
        <HUDWidget title="Memory">
          <div className="text-xs text-gray-400">Conv: {conversationIdRef.current ? '●' : '○'}</div>
          <div className="text-xs text-gray-400">Msgs: {messages.length}</div>
          <div className="text-xs text-violet-300/70 mt-1">15-yr advisor mode</div>
        </HUDWidget>
      </div>

      {/* Bottom controls */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-3 items-center titlebar-no-drag">
        <button onClick={onMicClick}
          className={`w-14 h-14 rounded-full border-2 flex items-center justify-center text-2xl transition-all
            ${recording ? 'bg-emerald-500/30 border-emerald-400 text-emerald-200 animate-pulse'
                       : 'bg-violet-700/20 border-violet-400/50 text-violet-200 hover:bg-violet-600/30'}`}>
          {recording ? '■' : '🎙'}
        </button>
        <button onClick={() => setShowText(s => !s)}
          className="w-12 h-12 rounded-full border border-cyan-500/40 text-cyan-300 hover:bg-cyan-700/20">
          ⌨
        </button>
      </div>

      {showText && (
        <form onSubmit={e => { e.preventDefault(); const t = textInput; setTextInput(''); setShowText(false); sendMessage(t) }}
              className="absolute bottom-24 left-1/2 -translate-x-1/2 w-[600px] titlebar-no-drag">
          <input autoFocus value={textInput} onChange={e => setTextInput(e.target.value)}
                 placeholder={`Ask ${profile.jarvisName} anything…`}
                 className="w-full bg-black/70 border border-violet-500/40 rounded-md px-4 py-3 text-violet-100 outline-none focus:border-violet-300" />
        </form>
      )}

      <UploadBar onResult={(r) => {
        const intro = r.kind === 'document' ? `I read "${r.name}".`
                    : r.kind === 'image'    ? `Took a look at the image you sent.`
                    : `I dug into ${r.name}.`
        const full = `${intro} ${r.text}`
        const id = Date.now() + 9
        setMessages(m => [...m, { id, role: 'assistant', content: full }])
        setOrbState('speak')
        speakText(full).then(a => { audioRef.current = a; a.onended = () => setOrbState('idle') }).catch(() => setOrbState('idle'))
      }} />
    </div>
  )
}

function Row({ k, v }) {
  return (
    <div className="flex justify-between text-xs my-0.5">
      <span className="text-gray-500">{k}</span>
      <span className="text-cyan-300">{v}</span>
    </div>
  )
}
