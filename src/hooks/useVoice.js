// src/hooks/useVoice.js — mic recording + amplitude meter
import { useEffect, useRef, useState, useCallback } from 'react'

export function useVoice() {
  const [recording, setRecording] = useState(false)
  const [amplitude, setAmplitude] = useState(0)
  const mediaRef = useRef(null)
  const recRef = useRef(null)
  const chunksRef = useRef([])
  const audioCtxRef = useRef(null)
  const rafRef = useRef(0)

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRef.current = stream
      chunksRef.current = []
      const rec = new MediaRecorder(stream)
      rec.ondataavailable = e => e.data.size && chunksRef.current.push(e.data)
      rec.start()
      recRef.current = rec

      // Amplitude meter
      const ac = new (window.AudioContext || window.webkitAudioContext)()
      const src = ac.createMediaStreamSource(stream)
      const an = ac.createAnalyser()
      an.fftSize = 512
      src.connect(an)
      audioCtxRef.current = ac
      const data = new Uint8Array(an.frequencyBinCount)
      const tick = () => {
        an.getByteTimeDomainData(data)
        let sum = 0
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128
          sum += v * v
        }
        setAmplitude(Math.min(1, Math.sqrt(sum / data.length) * 4))
        rafRef.current = requestAnimationFrame(tick)
      }
      tick()
      setRecording(true)
    } catch (e) {
      console.error('mic error', e)
    }
  }, [])

  const stop = useCallback(() => new Promise(resolve => {
    const rec = recRef.current
    if (!rec) return resolve(null)
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      mediaRef.current?.getTracks().forEach(t => t.stop())
      cancelAnimationFrame(rafRef.current)
      audioCtxRef.current?.close().catch(() => {})
      setAmplitude(0)
      setRecording(false)
      resolve(blob)
    }
    rec.stop()
  }), [])

  useEffect(() => () => {
    mediaRef.current?.getTracks().forEach(t => t.stop())
    cancelAnimationFrame(rafRef.current)
  }, [])

  return { recording, amplitude, start, stop }
}
