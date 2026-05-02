import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function TranscriptDisplay({ messages = [] }) {
  const last = messages.slice(-4)
  return (
    <div className="w-full max-w-3xl mx-auto px-4">
      <AnimatePresence initial={false}>
        {last.map((m, i) => {
          const isUser = m.role === 'user'
          return (
            <motion.div
              key={m.id || i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: i === last.length - 1 ? 1 : 0.5, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.4 }}
              className={`my-2 leading-relaxed ${isUser ? 'text-right text-gray-500 text-sm' : 'text-left text-gray-100'}`}
            >
              <span className={`text-[9px] tracking-[0.3em] mr-2 ${isUser ? 'text-emerald-400/60' : 'text-violet-400/70'}`}>
                {isUser ? 'YOU ›' : '‹ JARVIS'}
              </span>
              {m.content}
              {m.streaming && <span className="inline-block w-2 h-4 bg-violet-400 ml-1 animate-pulse" />}
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
