import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvis } from '../context/JarvisContext.jsx'
import Orb from './Orb.jsx'
import { research } from '../hooks/useJarvis.js'

const SUGGESTED = ['Aria', 'Nova', 'Atlas', 'Sage', 'Lyra', 'Echo']
const CHALLENGES = ['Low traffic', 'Bad conversion', 'No leads', 'High CAC',
                    'Weak brand', 'Other']

export default function Onboarding({ onComplete }) {
  const { profile, update } = useJarvis()
  const [step, setStep] = useState(0)
  const [loadingResults, setLoadingResults] = useState(null)

  async function runMarketAnalysis() {
    try {
      const r = await research({
        product: profile.product || 'general business',
        location: profile.location,
        business_type: profile.product || 'business',
        query: profile.product,
      })
      setLoadingResults(r)
    } catch (e) {
      setLoadingResults({ error: e.message })
    }
  }

  const next = () => setStep(s => s + 1)
  const back = () => setStep(s => Math.max(0, s - 1))

  return (
    <div className="w-full h-full bg-black hex-grid relative overflow-hidden flex items-center justify-center">
      <div className="scan-line" />
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-2xl px-8"
        >
          {step === 0 && (
            <div className="text-center">
              <div className="w-40 h-40 mx-auto mb-6 rounded-full border-2 border-violet-500/40 flex items-center justify-center"
                   style={{ boxShadow: '0 0 60px rgba(124,58,237,0.4)' }}>
                <div className="text-5xl">◉</div>
              </div>
              <h1 className="font-display text-4xl text-violet-200 tracking-wider mb-3">
                Meet Your Marketing Intelligence
              </h1>
              <p className="text-gray-400 mb-8">An AI strategist with 15 years of marketing expertise.</p>
              <Btn onClick={next}>Begin Setup</Btn>
            </div>
          )}

          {step === 1 && (
            <Step title="What should your AI be called?">
              <input value={profile.jarvisName}
                onChange={e => update({ jarvisName: e.target.value })}
                placeholder="Type a name…"
                className="w-full bg-black/60 border border-violet-500/40 rounded-md px-4 py-3 text-2xl text-violet-100 text-center outline-none focus:border-violet-300" />
              <div className="flex flex-wrap gap-2 justify-center mt-4">
                {SUGGESTED.map(n => (
                  <button key={n} onClick={() => update({ jarvisName: n })}
                    className="px-3 py-1 text-sm rounded-full border border-violet-500/30 text-violet-200 hover:bg-violet-700/20">
                    {n}
                  </button>
                ))}
              </div>
              <div className="mt-8 flex justify-center"><Orb name={profile.jarvisName} size={140} /></div>
              <Nav onBack={back} onNext={next} />
            </Step>
          )}

          {step === 2 && (
            <Step title={`What should ${profile.jarvisName} call you?`}>
              <input value={profile.userName}
                onChange={e => update({ userName: e.target.value })}
                placeholder="Your name…"
                className="w-full bg-black/60 border border-violet-500/40 rounded-md px-4 py-3 text-xl text-violet-100 text-center outline-none focus:border-violet-300" />
              <p className="text-gray-500 mt-4 text-center italic">
                {profile.jarvisName}: "Good morning, {profile.userName}. Ready to strategize?"
              </p>
              <Nav onBack={back} onNext={next} />
            </Step>
          )}

          {step === 3 && (
            <Step title="Your Business">
              <Field label="What do you sell?" value={profile.product} onChange={v => update({ product: v })} />
              <Field label="Who buys from you?" value={profile.audience} onChange={v => update({ audience: v })} />
              <Field label="Where are you based? (City, Country)" value={profile.location} onChange={v => update({ location: v })} />
              <TagField label="Main competitors" value={profile.competitors} onChange={v => update({ competitors: v })} />
              <Field label="Monthly marketing budget" value={profile.budget} onChange={v => update({ budget: v })} />
              <SelectField label="Biggest challenge" value={profile.challenge}
                options={CHALLENGES} onChange={v => update({ challenge: v })} />
              <Nav onBack={back} onNext={next} />
            </Step>
          )}

          {step === 4 && (
            <Step title="Connect your AI keys" subtitle="Stored only on your device. Never shared.">
              <div className="text-xs rounded-lg bg-blue-900/40 border border-blue-500/30 text-blue-200 px-3 py-2 mb-3">
                🎙 Wake word: Double-clap or tap the orb — no Porcupine key needed. OpenWakeWord (free, offline) handles spoken wake word automatically.
              </div>
              <KeyField label="Gemini API Key" value={profile.keys.gemini}
                onChange={v => update({ keys: { ...profile.keys, gemini: v } })}
                href="https://makersuite.google.com/app/apikey" required />
              <KeyField label="Groq API Key" value={profile.keys.groq}
                onChange={v => update({ keys: { ...profile.keys, groq: v } })}
                href="https://console.groq.com/keys" required />
              <KeyField label="DeepSeek API Key" value={profile.keys.deepseek}
                onChange={v => update({ keys: { ...profile.keys, deepseek: v } })}
                href="https://platform.deepseek.com" />
              <KeyField label="ElevenLabs API Key" value={profile.keys.elevenlabs}
                onChange={v => update({ keys: { ...profile.keys, elevenlabs: v } })}
                href="https://elevenlabs.io/app/settings/api-keys" />
              <KeyField label="Tavily API Key" value={profile.keys.tavily}
                onChange={v => update({ keys: { ...profile.keys, tavily: v } })}
                href="https://app.tavily.com" />
              <p className="text-xs text-gray-500 mt-3">
                Note: keys here are stored locally for reference. The backend reads keys from <code>backend/.env</code>.
              </p>
              <Nav onBack={back} onNext={next} />
            </Step>
          )}

          {step === 5 && (
            <Step title={`Analyzing ${profile.location} market…`}>
              <div className="flex justify-center my-8"><Orb state="think" name={profile.jarvisName} size={180} /></div>
              <LoadingCycle />
              <CountdownToAnalysis run={runMarketAnalysis} onDone={next} />
            </Step>
          )}

          {step === 6 && (
            <Step title={`${profile.jarvisName} is ready, ${profile.userName}.`}>
              <div className="flex justify-center my-6"><Orb state="speak" name={profile.jarvisName} size={180} /></div>
              <div className="grid grid-cols-3 gap-3">
                <Card title="Demand"
                      value={loadingResults?.demand_level || 'PENDING'}
                      sub={loadingResults?.demand_explanation?.slice(0, 60) || ''} />
                <Card title="Competitors"
                      value={`${(loadingResults?.competitors || []).length}`}
                      sub="found in your area" />
                <Card title="Top Channel"
                      value={loadingResults?.best_channels?.[0]?.channel || '—'}
                      sub="recommended" />
              </div>
              <div className="text-center mt-8">
                <Btn onClick={() => { update({ onboarded: true }); onComplete?.() }}>
                  Start Talking to {profile.jarvisName}
                </Btn>
              </div>
            </Step>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function Btn({ children, onClick, secondary }) {
  return (
    <button onClick={onClick}
      className={`titlebar-no-drag px-6 py-3 rounded-md font-display tracking-widest text-sm
        ${secondary ? 'border border-violet-500/40 text-violet-300 hover:bg-violet-700/20'
                    : 'bg-violet-600 text-white hover:bg-violet-500 shadow-lg shadow-violet-700/30'}`}>
      {children}
    </button>
  )
}

function Step({ title, subtitle, children }) {
  return (
    <div>
      <h2 className="font-display text-3xl text-violet-200 text-center mb-2">{title}</h2>
      {subtitle && <p className="text-center text-gray-500 mb-6">{subtitle}</p>}
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function Nav({ onBack, onNext, nextLabel = 'Continue' }) {
  return (
    <div className="flex justify-between mt-8">
      <Btn secondary onClick={onBack}>Back</Btn>
      <Btn onClick={onNext}>{nextLabel}</Btn>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text' }) {
  return (
    <div className="hud-border rounded-md p-3">
      <div className="text-[10px] tracking-[0.3em] text-cyan-400/70 uppercase mb-1">{label}</div>
      <input type={type} value={value || ''} onChange={e => onChange(e.target.value)}
        className="w-full bg-transparent text-violet-100 outline-none" />
    </div>
  )
}

function SelectField({ label, value, options, onChange }) {
  return (
    <div className="hud-border rounded-md p-3">
      <div className="text-[10px] tracking-[0.3em] text-cyan-400/70 uppercase mb-1">{label}</div>
      <select value={value || ''} onChange={e => onChange(e.target.value)}
        className="w-full bg-black text-violet-100 outline-none">
        <option value="">— select —</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

function TagField({ label, value, onChange }) {
  const [t, setT] = useState('')
  const tags = value || []
  return (
    <div className="hud-border rounded-md p-3">
      <div className="text-[10px] tracking-[0.3em] text-cyan-400/70 uppercase mb-1">{label}</div>
      <div className="flex flex-wrap gap-2 mb-2">
        {tags.map((x, i) => (
          <span key={i} className="px-2 py-0.5 text-xs rounded-full bg-violet-700/30 text-violet-200">
            {x}
            <button className="ml-2 text-violet-400" onClick={() => onChange(tags.filter((_, j) => j !== i))}>×</button>
          </span>
        ))}
      </div>
      <input value={t} onChange={e => setT(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && t.trim()) { onChange([...tags, t.trim()]); setT('') } }}
        placeholder="type and press Enter…"
        className="w-full bg-transparent text-violet-100 outline-none" />
    </div>
  )
}

function KeyField({ label, value, onChange, href, required }) {
  const status = value ? '🟢' : (required ? '🔴' : '🟡')
  return (
    <div className="hud-border rounded-md p-3">
      <div className="flex items-center justify-between text-[10px] tracking-[0.3em] text-cyan-400/70 uppercase mb-1">
        <span>{label} {required && <span className="text-red-400">*</span>}</span>
        <a href={href} target="_blank" rel="noreferrer" className="text-violet-300 normal-case tracking-normal">Get key ↗</a>
      </div>
      <div className="flex items-center gap-2">
        <span>{status}</span>
        <input value={value || ''} onChange={e => onChange(e.target.value)}
          placeholder="paste key…" type="password"
          className="w-full bg-transparent text-violet-100 outline-none" />
      </div>
    </div>
  )
}

function Card({ title, value, sub }) {
  return (
    <div className="hud-border rounded-md p-3 text-center">
      <div className="text-[10px] tracking-[0.3em] text-cyan-400/70 uppercase">{title}</div>
      <div className="text-xl text-violet-200 my-2">{value}</div>
      <div className="text-[10px] text-gray-500">{sub}</div>
    </div>
  )
}

function LoadingCycle() {
  const phrases = [
    'Searching market data for your product…',
    'Analyzing competitors in your city…',
    'Identifying best marketing channels…',
    'Building your intelligence profile…',
  ]
  const [i, setI] = useState(0)
  React.useEffect(() => {
    const id = setInterval(() => setI(x => (x + 1) % phrases.length), 2500)
    return () => clearInterval(id)
  }, [])
  return <div className="text-center text-cyan-300/80 my-3">{phrases[i]}</div>
}

function CountdownToAnalysis({ run, onDone }) {
  React.useEffect(() => {
    let cancelled = false
    const t = setTimeout(async () => {
      await run().catch(() => {})
      if (!cancelled) onDone()
    }, 800)
    return () => { cancelled = true; clearTimeout(t) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return null
}
