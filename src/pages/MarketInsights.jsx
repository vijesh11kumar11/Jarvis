import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJarvis } from '../context/JarvisContext.jsx'
import { research, generateIdeas, evaluateIdea } from '../hooks/useJarvis.js'

const IDEA_MODES = [
  { id: 'viral',       label: 'Viral' },
  { id: 'community',   label: 'Community' },
  { id: 'content',     label: 'Content' },
  { id: 'partnership', label: 'Partnership' },
  { id: 'guerrilla',   label: 'Guerrilla' },
]

export default function MarketInsights() {
  const { profile } = useJarvis()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      const r = await research({
        product: profile.product || 'business',
        location: profile.location,
        business_type: profile.product || 'business',
        query: profile.product || 'market overview',
      })
      setReport(r)
    } finally { setLoading(false) }
  }

  useEffect(() => { refresh() /* on mount */ }, []) // eslint-disable-line

  return (
    <div className="p-8 h-full overflow-y-auto hex-grid">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display text-3xl text-violet-200">Market Insights</h1>
        <button onClick={refresh}
          className="titlebar-no-drag px-4 py-2 rounded border border-violet-500/40 text-violet-200 hover:bg-violet-700/20">
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
      {!report ? (
        <p className="text-gray-400">No data yet. Add your product in Settings, then refresh.</p>
      ) : (
        <div className="space-y-4">
          <Section title="Demand">
            <p className="text-violet-200 text-xl">{report.demand_level}</p>
            <p className="text-gray-300">{report.demand_explanation}</p>
          </Section>
          <Section title="Competitors">
            <ul>{(report.competitors || []).map((c, i) =>
              <li key={i} className="text-gray-200">• <b>{c.name}</b> — {c.strength} / weak: {c.weakness}</li>)}
            </ul>
          </Section>
          <Section title="Pricing">
            <pre className="text-cyan-300 text-sm">{JSON.stringify(report.pricing, null, 2)}</pre>
          </Section>
          <Section title="Best Channels">
            {(report.best_channels || []).map((c, i) =>
              <div key={i} className="text-gray-200">• <b>{c.channel}</b> — {c.why}</div>)}
          </Section>
          <Section title="Opportunities">
            {(report.opportunities || []).map((o, i) =>
              <div key={i} className="text-emerald-300">▲ {o}</div>)}
          </Section>
          <Section title="Threats">
            {(report.threats || []).map((o, i) =>
              <div key={i} className="text-red-300">▼ {o}</div>)}
          </Section>
          <Section title="Executive Summary">
            <p className="text-gray-200 leading-relaxed">{report.summary}</p>
          </Section>
        </div>
      )}
      <IdeasLab profile={profile} />
    </div>
  )
}

function IdeasLab({ profile }) {
  const [topic, setTopic] = useState('')
  const [mode, setMode] = useState('viral')
  const [ideas, setIdeas] = useState([])
  const [loading, setLoading] = useState(false)
  const [verdicts, setVerdicts] = useState({})

  async function go() {
    if (!topic.trim()) return
    setLoading(true); setIdeas([]); setVerdicts({})
    try {
      const r = await generateIdeas({
        user_id: profile.userId || 'anonymous',
        topic, mode, count: 5,
      })
      setIdeas(r.ideas || [])
    } finally { setLoading(false) }
  }

  async function evalOne(idx, idea) {
    setVerdicts(v => ({ ...v, [idx]: { loading: true } }))
    const r = await evaluateIdea({ user_id: profile.userId || 'anonymous', idea })
    setVerdicts(v => ({ ...v, [idx]: r }))
  }

  return (
    <div className="mt-10">
      <h2 className="font-display text-2xl text-violet-200 mb-3">Ideas Lab</h2>
      <div className="flex gap-2 mb-3 flex-wrap">
        <input value={topic} onChange={e => setTopic(e.target.value)}
               placeholder="What are we ideating? e.g., launch a Coimbatore coffee brand"
               className="flex-1 min-w-[260px] bg-black/40 border border-white/15
                          rounded px-3 py-2 text-violet-100 placeholder-white/30" />
        <select value={mode} onChange={e => setMode(e.target.value)}
                className="bg-black/40 border border-white/15 rounded px-3 py-2 text-violet-100">
          {IDEA_MODES.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
        </select>
        <button onClick={go}
                className="px-4 py-2 rounded border border-violet-500/40 text-violet-100 hover:bg-violet-700/30">
          {loading ? 'Generating…' : 'Generate'}
        </button>
      </div>

      <AnimatePresence>
        <div className="grid md:grid-cols-2 gap-3">
          {ideas.map((idea, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="hud-border rounded-md p-4 bg-black/30">
              <div className="text-violet-200 font-semibold">{idea.name}</div>
              <div className="text-xs text-white/60 mb-2">{idea.tagline}</div>
              <div className="text-sm text-white/80 mb-2">{idea.the_insight}</div>
              {(idea.execution || []).map((s, j) => (
                <div key={j} className="text-xs text-emerald-200/80">• {s}</div>
              ))}
              <div className="mt-2 text-[11px] text-cyan-300/80">
                Goal: {idea.success_metric} · {idea.time_to_first_results}
              </div>
              <div className="mt-2 flex gap-2 items-center">
                <button onClick={() => evalOne(i, idea)}
                        className="text-xs px-2 py-1 rounded border border-white/20 text-white/80 hover:bg-white/10">
                  {verdicts[i]?.loading ? 'Evaluating…' : 'Evaluate'}
                </button>
                {verdicts[i]?.verdict && (
                  <span className={
                    verdicts[i].verdict === 'GREEN' ? 'text-emerald-400' :
                    verdicts[i].verdict === 'RED'   ? 'text-red-400' :
                                                      'text-amber-300'}>
                    {verdicts[i].verdict} · {verdicts[i].why}
                  </span>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </AnimatePresence>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="hud-border rounded-md p-4">
      <div className="text-[10px] tracking-[0.3em] text-cyan-400/70 uppercase mb-2">{title}</div>
      {children}
    </div>
  )
}
