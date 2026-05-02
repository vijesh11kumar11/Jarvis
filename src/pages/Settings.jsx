import React from 'react'
import { useJarvis } from '../context/JarvisContext.jsx'

export default function Settings() {
  const { profile, update, setProfile } = useJarvis()
  return (
    <div className="p-8 h-full overflow-y-auto hex-grid space-y-4">
      <h1 className="font-display text-3xl text-violet-200">Settings</h1>

      <Section title="Jarvis Identity">
        <Text label="Jarvis Name" value={profile.jarvisName} onChange={v => update({ jarvisName: v })} />
        <Text label="Wake Mode (hotkey | word | clap)" value={profile.wakeMode} onChange={v => update({ wakeMode: v })} />
      </Section>

      <Section title="Your Profile">
        <Text label="Your Name" value={profile.userName} onChange={v => update({ userName: v })} />
        <Text label="Location" value={profile.location} onChange={v => update({ location: v })} />
      </Section>

      <Section title="Business Context">
        <Text label="Product / Service" value={profile.product} onChange={v => update({ product: v })} />
        <Text label="Target Audience" value={profile.audience} onChange={v => update({ audience: v })} />
        <Text label="Budget" value={profile.budget} onChange={v => update({ budget: v })} />
        <Text label="Competitors (comma)" value={(profile.competitors || []).join(', ')}
              onChange={v => update({ competitors: v.split(',').map(s => s.trim()).filter(Boolean) })} />
      </Section>

      <Section title="API Keys (local reference)">
        {Object.entries(profile.keys || {}).map(([k, v]) => (
          <Text key={k} label={k} value={v}
            onChange={val => update({ keys: { ...profile.keys, [k]: val } })} />
        ))}
        <p className="text-xs text-gray-500 mt-2">
          The backend reads keys from <code>backend/.env</code>. Update that file directly when you change keys.
        </p>
      </Section>

      <Section title="Data & Privacy">
        <button onClick={() => { if (confirm('Reset all local data?')) {
            localStorage.removeItem('jarvis_profile_v1')
            location.reload()
          }}}
          className="px-4 py-2 rounded border border-red-500/40 text-red-300 hover:bg-red-900/20">
          Reset All Local Data
        </button>
      </Section>

      <Section title="About">
        <p className="text-gray-400 text-sm">
          Marketing Jarvis v1.0 — built with Gemini + Groq.
        </p>
      </Section>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="hud-border rounded-md p-4 space-y-2">
      <div className="text-[10px] tracking-[0.3em] text-cyan-400/70 uppercase mb-2">{title}</div>
      {children}
    </div>
  )
}

function Text({ label, value, onChange }) {
  return (
    <label className="block">
      <span className="text-xs text-gray-500">{label}</span>
      <input value={value || ''} onChange={e => onChange(e.target.value)}
        className="w-full bg-black/60 border border-violet-700/40 rounded-md px-3 py-2 text-violet-100 outline-none focus:border-violet-300" />
    </label>
  )
}
