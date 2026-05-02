import React, { useEffect, useState } from 'react'
import { useJarvis } from '../context/JarvisContext.jsx'
import { research } from '../hooks/useJarvis.js'

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
