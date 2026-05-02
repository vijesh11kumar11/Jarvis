import React, { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  uploadDocument, analyzeGithub, visionChat, fileToBase64,
} from '../hooks/useJarvis.js'
import { useJarvis } from '../context/JarvisContext.jsx'

export default function UploadBar({ onResult }) {
  const { profile } = useJarvis()
  const [busy, setBusy] = useState('')
  const [showRepo, setShowRepo] = useState(false)
  const [repoUrl, setRepoUrl] = useState('')
  const docRef = useRef(null)
  const imgRef = useRef(null)

  const userId = profile.userId || 'local'

  async function handleDoc(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy('doc')
    try {
      const r = await uploadDocument(file, userId)
      onResult?.({
        kind: 'document', name: file.name,
        text: r.analysis || '(no analysis)',
      })
    } finally { setBusy(''); e.target.value = '' }
  }

  async function handleImg(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setBusy('img')
    try {
      const b64 = await fileToBase64(file)
      const r = await visionChat({
        user_id: userId,
        jarvis_name: profile.jarvisName,
        user_name: profile.userName,
        image_b64: b64,
        prompt: `Look at this image and react as my marketing CMO friend.`,
      })
      onResult?.({
        kind: 'image', name: file.name,
        text: r.answer || '(no analysis)',
      })
    } finally { setBusy(''); e.target.value = '' }
  }

  async function handleRepo() {
    if (!repoUrl.trim()) return
    setBusy('repo')
    try {
      const r = await analyzeGithub({ user_id: userId, url: repoUrl.trim() })
      if (r.error) {
        onResult?.({ kind: 'github', name: repoUrl, text: r.error })
      } else {
        const b = r.brief || {}
        onResult?.({
          kind: 'github', name: `${b.owner}/${b.repo}`,
          text: r.analysis || '(no analysis)',
        })
      }
      setRepoUrl(''); setShowRepo(false)
    } finally { setBusy('') }
  }

  return (
    <div className="absolute bottom-4 right-6 flex gap-2 items-center titlebar-no-drag">
      <input ref={docRef} type="file" hidden onChange={handleDoc}
             accept=".pdf,.docx,.txt,.md,.json,.py,.js,.ts,.tsx,.jsx,.html,.css,.yaml,.yml,.toml,.csv" />
      <input ref={imgRef} type="file" hidden accept="image/*" onChange={handleImg} />

      <IconBtn label="Upload document" busy={busy === 'doc'}
               onClick={() => docRef.current?.click()}>📄</IconBtn>
      <IconBtn label="Send image" busy={busy === 'img'}
               onClick={() => imgRef.current?.click()}>🖼</IconBtn>
      <IconBtn label="Analyse GitHub repo" busy={busy === 'repo'}
               onClick={() => setShowRepo(s => !s)}>🐙</IconBtn>

      <AnimatePresence>
        {showRepo && (
          <motion.form
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            onSubmit={e => { e.preventDefault(); handleRepo() }}
            className="absolute bottom-14 right-0 bg-black/90 border border-violet-500/40 rounded-md p-2 flex gap-2 w-[320px]">
            <input autoFocus value={repoUrl}
                   onChange={e => setRepoUrl(e.target.value)}
                   placeholder="https://github.com/owner/repo"
                   className="flex-1 bg-black/60 border border-violet-700/40 rounded px-2 py-1 text-sm text-violet-100 outline-none" />
            <button type="submit"
              className="px-2 py-1 text-sm rounded bg-violet-600/40 border border-violet-300/40 text-violet-100">
              {busy === 'repo' ? '…' : 'Go'}
            </button>
          </motion.form>
        )}
      </AnimatePresence>
    </div>
  )
}

function IconBtn({ children, onClick, busy, label }) {
  return (
    <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}
      title={label} onClick={onClick}
      className={`w-11 h-11 rounded-full border flex items-center justify-center text-lg
        ${busy ? 'bg-amber-500/30 border-amber-300/60 animate-pulse'
               : 'bg-black/60 border-violet-500/40 text-violet-200 hover:bg-violet-700/20'}`}>
      {children}
    </motion.button>
  )
}
