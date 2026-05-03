/* src/hooks/useVoice.js
 * Browser-side voice I/O for Friday: getUserMedia → MediaRecorder → backend /listen
 * Web Audio AnalyserNode → amplitude + frequency bins for the orb / avatar.
 * Audio playback for /speak responses with onended callbacks.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export function useVoice({ apiBase = "http://localhost:8000" } = {}) {
  const [recording, setRecording] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [amplitude, setAmplitude] = useState(0);
  const [frequencies, setFrequencies] = useState(new Float32Array(64));
  const mediaRef = useRef(null);
  const recorderRef = useRef(null);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(0);
  const audioElRef = useRef(null);
  const chunksRef = useRef([]);

  const _ensureAnalyser = (sourceNode) => {
    const ctx = audioCtxRef.current ||
      new (window.AudioContext || window.webkitAudioContext)();
    audioCtxRef.current = ctx;
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 128;
    sourceNode.connect(analyser);
    analyserRef.current = analyser;
    const buf = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(buf);
      let sum = 0;
      const out = new Float32Array(buf.length);
      for (let i = 0; i < buf.length; i++) {
        out[i] = buf[i] / 255;
        sum += buf[i];
      }
      const avg = sum / buf.length / 255;
      setAmplitude(avg);
      setFrequencies(out);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  const _stopAnalyser = () => {
    cancelAnimationFrame(rafRef.current);
    setAmplitude(0);
  };

  const startListening = useCallback(async () => {
    if (recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRef.current = stream;
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      _ensureAnalyser(src);

      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data && chunksRef.current.push(e.data);
      rec.start(100);
      recorderRef.current = rec;
      setRecording(true);
    } catch (e) {
      console.error("[voice] mic permission failed", e);
    }
  }, [recording]);

  const stopListening = useCallback(async () => {
    return new Promise((resolve) => {
      const rec = recorderRef.current;
      if (!rec) return resolve(null);
      rec.onstop = async () => {
        _stopAnalyser();
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        try {
          const fd = new FormData();
          fd.append("audio", blob, "rec.webm");
          const r = await fetch(`${apiBase}/listen`, { method: "POST", body: fd });
          const data = await r.json();
          resolve(data);
        } catch (e) {
          console.error("[voice] /listen failed", e);
          resolve({ text: "", error: String(e) });
        } finally {
          if (mediaRef.current) {
            mediaRef.current.getTracks().forEach(t => t.stop());
            mediaRef.current = null;
          }
          recorderRef.current = null;
          setRecording(false);
        }
      };
      rec.stop();
    });
  }, [apiBase]);

  const playAudio = useCallback(async (text, voiceId, onEnd) => {
    if (!text) { onEnd?.(); return; }
    try {
      setPlaying(true);
      const res = await fetch(`${apiBase}/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice_id: voiceId || null }),
      });
      const buffer = await res.arrayBuffer();
      const blob = new Blob([buffer], { type: "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      const el = new Audio(url);
      audioElRef.current = el;

      // Hook playback through analyser
      const ctx = audioCtxRef.current ||
        new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = ctx;
      try {
        const src = ctx.createMediaElementSource(el);
        src.connect(ctx.destination);
        _ensureAnalyser(src);
      } catch { /* fallback: direct play */ }

      el.onended = () => {
        _stopAnalyser();
        setPlaying(false);
        URL.revokeObjectURL(url);
        onEnd?.();
      };
      el.onerror = () => {
        _stopAnalyser();
        setPlaying(false);
        onEnd?.();
      };
      await el.play();
    } catch (e) {
      console.error("[voice] playAudio failed", e);
      setPlaying(false);
      onEnd?.();
    }
  }, [apiBase]);

  const stopPlaying = useCallback(() => {
    if (audioElRef.current) {
      audioElRef.current.pause();
      audioElRef.current = null;
    }
    _stopAnalyser();
    setPlaying(false);
  }, []);

  useEffect(() => () => {
    cancelAnimationFrame(rafRef.current);
    if (mediaRef.current) mediaRef.current.getTracks().forEach(t => t.stop());
  }, []);

  return {
    recording, playing, amplitude, frequencies,
    startListening, stopListening, playAudio, stopPlaying,
  };
}

export default useVoice;
