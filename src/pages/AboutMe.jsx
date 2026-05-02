import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useJarvis } from '../context/JarvisContext.jsx'
import { getAboutMe, saveAboutMe } from '../hooks/useJarvis.js'

export default function AboutMe() {
  const { profile } = useJarvis()
  const userId = profile.userId || 'local'
  const [form, setForm] = useState({ life_story: '', preferences: '', facts: '' })
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAboutMe(userId).then(d => {
      setForm({
        life_story: d.life_story || '',
        preferences: d.preferences || '',
        facts: d.facts || '',
      })
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [userId])

  async function save() {
    setStatus('saving…')
    try {
      await saveAboutMe({ user_id: userId, ...form })
      setStatus('saved ✓')
      setTimeout(() => setStatus(''), 2000)
    } catch (e) {
      setStatus('failed')
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full h-full overflow-y-auto p-8 hex-grid">
      <div className="scan-line" />
      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-display text-violet-200 tracking-wider">
            About {profile.userName}
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Tell {profile.jarvisName} about yourself — your story, what you love,
            what you hate, your dreams. The more I know, the better friend I can be.
          </p>
        </div>

        {loading ? <div className="text-gray-500">loading…</div> : (
          <>
            <Field label="Your life story (background, journey, milestones)">
              <textarea rows={10} value={form.life_story}
                onChange={e => setForm(f => ({ ...f, life_story: e.target.value }))}
                placeholder="I grew up in… My turning point was… Today I'm building…"
                className="w-full bg-black/70 border border-violet-500/30 rounded-md p-3 text-violet-100 text-sm outline-none focus:border-violet-300 resize-y" />
            </Field>
            <Field label="Preferences (tone, hobbies, working style, what motivates you)">
              <textarea rows={5} value={form.preferences}
                onChange={e => setForm(f => ({ ...f, preferences: e.target.value }))}
                placeholder="I prefer plain-spoken advice, no jargon. I work best at night. I love…"
                className="w-full bg-black/70 border border-violet-500/30 rounded-md p-3 text-violet-100 text-sm outline-none focus:border-violet-300 resize-y" />
            </Field>
            <Field label="Other facts I should remember">
              <textarea rows={4} value={form.facts}
                onChange={e => setForm(f => ({ ...f, facts: e.target.value }))}
                placeholder="My partner is a designer. Anniversary is in March. I drink filter coffee."
                className="w-full bg-black/70 border border-violet-500/30 rounded-md p-3 text-violet-100 text-sm outline-none focus:border-violet-300 resize-y" />
            </Field>
            <div className="flex items-center gap-3">
              <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                onClick={save}
                className="px-4 py-2 rounded-md bg-violet-600/40 border border-violet-300/40 text-violet-100">
                Save
              </motion.button>
              <span className="text-sm text-emerald-300">{status}</span>
            </div>
          </>
        )}
      </div>
    </motion.div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-violet-300 mb-2">{label}</div>
      {children}
    </div>
  )
}
