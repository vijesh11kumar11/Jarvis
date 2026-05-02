import React, { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from './components/Sidebar.jsx'
import Onboarding from './components/Onboarding.jsx'
import JarvisChat from './pages/JarvisChat.jsx'
import MarketInsights from './pages/MarketInsights.jsx'
import Settings from './pages/Settings.jsx'
import AboutMe from './pages/AboutMe.jsx'
import { useJarvis } from './context/JarvisContext.jsx'
import { health } from './hooks/useJarvis.js'

export default function App() {
  const { profile } = useJarvis()
  const [booting, setBooting] = useState(true)
  const [backendOk, setBackendOk] = useState(false)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const h = await health()
      if (alive && h.ok) setBackendOk(true)
      else if (alive) setTimeout(tick, 1000)
    }
    tick()
    const t = setTimeout(() => setBooting(false), 3500)
    return () => { alive = false; clearTimeout(t) }
  }, [])

  return (
    <div className="w-screen h-screen bg-black text-white relative overflow-hidden">
      <TitleBar />
      {booting ? <BootScreen /> : (
        !profile.onboarded ? (
          <Onboarding onComplete={() => location.hash = '#/'} />
        ) : (
          <div className="flex h-[calc(100vh-32px)]">
            <Sidebar />
            <div className="flex-1 relative">
              <Routes>
                <Route path="/" element={<JarvisChat />} />
                <Route path="/insights" element={<MarketInsights />} />
                <Route path="/about-me" element={<AboutMe />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" />} />
              </Routes>
              {!backendOk && (
                <div className="absolute bottom-2 right-2 text-xs text-amber-400/80 bg-black/60 px-2 py-1 rounded">
                  ⚠ Backend connecting…
                </div>
              )}
            </div>
          </div>
        )
      )}
    </div>
  )
}

function TitleBar() {
  return (
    <div className="titlebar-drag h-8 flex items-center justify-between px-3 bg-black/80 border-b border-violet-900/30 text-xs text-gray-500">
      <div className="font-display tracking-widest text-violet-300">MARKETING JARVIS</div>
      <div className="titlebar-no-drag flex gap-2">
        <button onClick={() => window.jarvis?.windowControl('minimize')} className="hover:text-white px-2">–</button>
        <button onClick={() => window.jarvis?.windowControl('maximize')} className="hover:text-white px-2">▢</button>
        <button onClick={() => window.jarvis?.windowControl('close')} className="hover:text-red-400 px-2">×</button>
      </div>
    </div>
  )
}

function BootScreen() {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-black hex-grid">
      <div className="scan-line" />
      <AnimatePresence>
        <motion.div
          key="boot"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 1.2 }}
          className="w-48 h-48 rounded-full border border-violet-500/40"
          style={{ boxShadow: '0 0 80px rgba(124,58,237,0.5)' }}
        >
          <div className="w-full h-full flex items-center justify-center text-violet-200 font-display tracking-widest">
            INITIALIZING
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
