import React, { createContext, useContext, useEffect, useState } from 'react'
import { DEFAULT_JARVIS_NAME, DEFAULT_USER_NAME, DEFAULT_LOCATION } from '../config'

const JarvisContext = createContext(null)

const STORAGE_KEY = 'jarvis_profile_v2'

export function JarvisProvider({ children }) {
  const [profile, setProfile] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) return JSON.parse(raw)
    } catch {}
    return {
      onboarded: false,
      jarvisName: DEFAULT_JARVIS_NAME,
      userName: DEFAULT_USER_NAME,
      location: DEFAULT_LOCATION,
      product: '',
      audience: '',
      competitors: [],
      budget: 'INR 25,000 / month',
      challenge: '',
      keys: { gemini: '', groq: '', elevenlabs: '', tavily: '', porcupine: '' },
      wakeMode: 'hotkey', // 'hotkey' | 'word' | 'clap'
    }
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  }, [profile])

  const update = (patch) => setProfile(p => ({ ...p, ...patch }))

  return (
    <JarvisContext.Provider value={{ profile, update, setProfile }}>
      {children}
    </JarvisContext.Provider>
  )
}

export function useJarvis() {
  const ctx = useContext(JarvisContext)
  if (!ctx) throw new Error('useJarvis must be inside JarvisProvider')
  return ctx
}
