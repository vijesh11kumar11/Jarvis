import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const STATES = {
  idle:    { color: '#7C3AED', glow: 'orb-glow-idle',   ring: '#7C3AED', label: 'IDLE' },
  listen:  { color: '#10B981', glow: 'orb-glow-listen', ring: '#10B981', label: 'LISTENING' },
  think:   { color: '#3B82F6', glow: 'orb-glow-think',  ring: '#3B82F6', label: 'THINKING' },
  speak:   { color: '#A78BFA', glow: 'orb-glow-speak',  ring: '#A78BFA', label: 'SPEAKING' },
}

export default function Orb({ state = 'idle', name = 'Aria', amplitude = 0, size = 280 }) {
  const s = STATES[state] || STATES.idle
  const scale = state === 'listen' ? 1 + amplitude * 0.18 :
                state === 'speak'  ? 1 + amplitude * 0.12 : 1

  return (
    <div className="flex flex-col items-center justify-center select-none">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Outer dashed ring (slow CW) */}
        <div className="absolute inset-0 rounded-full border-2 border-dashed animate-spinslow"
             style={{ borderColor: `${s.ring}55` }} />
        {/* Middle ring (CCW) */}
        <div className="absolute inset-4 rounded-full animate-spinrev"
             style={{ background: `conic-gradient(from 0deg, transparent 25%, ${s.ring}aa 50%, transparent 75%)`, mask: 'radial-gradient(circle, transparent 60%, black 62%)', WebkitMask: 'radial-gradient(circle, transparent 60%, black 62%)' }} />
        {/* Inner pulsing ring */}
        <motion.div
          className="absolute inset-8 rounded-full border"
          animate={{ opacity: state === 'listen' ? [0.4, 1, 0.4] : [0.5, 0.9, 0.5] }}
          transition={{ duration: state === 'listen' ? 0.6 : 2.5, repeat: Infinity }}
          style={{ borderColor: s.ring }}
        />
        {/* Core */}
        <motion.div
          className={`absolute inset-12 rounded-full ${s.glow}`}
          style={{
            background: `radial-gradient(circle at 30% 30%, ${s.color}cc, ${s.color}33 60%, #000 100%)`,
          }}
          animate={{ scale }}
          transition={{ duration: 0.25 }}
        />
        {/* Speaking ripples */}
        <AnimatePresence>
          {state === 'speak' && [0, 1, 2].map(i => (
            <motion.div
              key={i}
              className="absolute inset-12 rounded-full border"
              style={{ borderColor: `${s.ring}66` }}
              initial={{ scale: 1, opacity: 0.7 }}
              animate={{ scale: 1.6, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.4 }}
            />
          ))}
        </AnimatePresence>
        {/* Orbiting particles */}
        {Array.from({ length: 10 }).map((_, i) => {
          const r = 60 + (i % 3) * 30
          const dur = 6 + (i % 5) * 2
          return (
            <div
              key={i}
              className="absolute inset-0"
              style={{ animation: `spinslow ${dur}s linear infinite`, animationDelay: `${-i * 0.6}s` }}
            >
              <div className="absolute rounded-full"
                   style={{
                     width: 4, height: 4,
                     background: s.ring,
                     boxShadow: `0 0 8px ${s.ring}`,
                     left: `calc(50% + ${r}px)`,
                     top: '50%',
                     transform: 'translate(-50%, -50%)',
                     opacity: 0.7,
                   }} />
            </div>
          )
        })}
      </div>
      <div className="mt-6 text-center">
        <div className="text-2xl font-display tracking-widest" style={{ color: s.ring }}>
          {name.toUpperCase()}
        </div>
        <div className="text-[10px] tracking-[0.4em] mt-1 text-gray-500">{s.label}</div>
      </div>
    </div>
  )
}
