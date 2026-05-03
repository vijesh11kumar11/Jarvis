/* src/pages/JarvisChat.jsx
 * Voice-only conversation surface for Friday.
 * Startup sequence → idle → wake → listen → think → speak → idle.
 * Tap-to-talk + push-to-hold + auto wake-word + double-clap.
 * Avatar + Orb both react to amplitude.
 */
import React, { useEffect, useReducer, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Orb from "../components/Orb.jsx";
import Avatar from "../components/Avatar.jsx";
import UploadBar from "../components/UploadBar.jsx";
import { useVoice } from "../hooks/useVoice.js";
import { useJarvisAPI } from "../hooks/useJarvis.js";
import { useJarvis } from "../context/JarvisContext.jsx";

const STATES = {
  STARTUP: "STARTUP",
  IDLE: "IDLE",
  WAKE_DETECTED: "WAKE_DETECTED",
  LISTENING: "LISTENING",
  PROCESSING: "PROCESSING",
  THINKING: "THINKING",
  SPEAKING: "SPEAKING",
  CONFIRMING: "CONFIRMING",
  ERROR: "ERROR",
};

function reducer(state, action) {
  switch (action.type) {
    case "set":      return { ...state, ...action.payload };
    case "transcript": return { ...state, lastUser: action.payload };
    case "reply":    return { ...state, lastAssistant: action.payload };
    case "status":   return { ...state, status: action.payload };
    default:         return state;
  }
}

const initial = {
  status: STATES.STARTUP,
  lastUser: "",
  lastAssistant: "",
  transcript: [],   // { role, text } []
  followUp: false,
  showAvatar: localStorage.getItem("jarvis_show_avatar") !== "false",
};

export default function JarvisChat() {
  const { profile } = useJarvis();
  const userId = profile?.userId || "anonymous";
  const [s, dispatch] = useReducer(reducer, initial);
  const setStatus = (status) => dispatch({ type: "status", payload: status });

  const voice = useVoice();
  const api = useJarvisAPI({
    userId,
    jarvisName: profile.jarvisName,
    userName: profile.userName,
  });

  const wakeSrcRef = useRef(null);
  const briefingPlayedRef = useRef(false);

  // ── Startup sequence ──
  useEffect(() => {
    const t1 = setTimeout(() => setStatus(STATES.IDLE), 2500);
    return () => clearTimeout(t1);
  }, []);

  // ── Morning briefing once after first IDLE (if today not greeted) ──
  useEffect(() => {
    if (s.status !== STATES.IDLE || briefingPlayedRef.current) return;
    briefingPlayedRef.current = true;
    (async () => {
      try {
        if (userId === "anonymous") {
          await speak(`Hey ${profile.userName}, I'm ${profile.jarvisName}. Tap the orb or say "hey jarvis" whenever you want to talk.`);
          return;
        }
        const brief = await api.triggerMorningBriefing();
        if (brief?.spoken) await speak(brief.spoken);
      } catch (e) { console.warn("[chat] briefing skipped", e); }
    })();
    // eslint-disable-next-line
  }, [s.status]);

  // ── Wake-word SSE ──
  useEffect(() => {
    let sse;
    try {
      // best-effort: enable wake listeners on backend
      fetch("http://localhost:8000/wake-word/start", { method: "POST" })
        .catch(() => {});
      sse = new EventSource("http://localhost:8000/wake-word/events");
      sse.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data || "{}");
          wakeSrcRef.current = data.source || "any";
          if (s.status === STATES.IDLE || s.status === STATES.SPEAKING) {
            handleWake();
          }
        } catch {}
      };
    } catch {}
    return () => { try { sse?.close(); } catch {} };
    // eslint-disable-next-line
  }, [s.status]);

  // ── Core action: speak then return to IDLE (or LISTENING if follow-up) ──
  async function speak(text) {
    if (!text) return;
    setStatus(STATES.SPEAKING);
    await new Promise((resolve) => {
      voice.playAudio(text, profile?.voiceId, () => {
        if (s.followUp) setTimeout(() => beginListening(), 300);
        else setStatus(STATES.IDLE);
        resolve();
      });
    });
  }

  async function beginListening() {
    setStatus(STATES.LISTENING);
    await voice.startListening();
  }

  async function handleWake() {
    if (voice.playing) voice.stopPlaying();
    await beginListening();
  }

  async function endListeningAndProcess() {
    setStatus(STATES.PROCESSING);
    const result = await voice.stopListening();
    const text = (result?.text || "").trim();
    if (!text) {
      setStatus(STATES.IDLE);
      return;
    }
    dispatch({ type: "transcript", payload: text });
    dispatch({ type: "set", payload: { transcript: [...s.transcript, { role: "user", text }] } });

    setStatus(STATES.THINKING);
    let acc = "";
    await api.chat(text, {
      onDelta: (_d, full) => { acc = full; },
      onDone: async (full) => {
        dispatch({ type: "reply", payload: full });
        dispatch({ type: "set", payload: {
          transcript: [...s.transcript, { role: "user", text },
                                       { role: "assistant", text: full }],
        }});
        if (api.pendingAction) {
          setStatus(STATES.CONFIRMING);
          await speak(api.pendingAction.speak ||
            "I want to take an action. Should I go ahead? Say yes or no.");
        } else {
          await speak(full);
        }
      },
      onError: async (err) => {
        await speak(`Hmm, something broke: ${err}`);
      },
    });
    if (!acc) setStatus(STATES.IDLE);
  }

  // ── Tap orb to toggle listening ──
  async function onOrbTap() {
    if (s.status === STATES.LISTENING) {
      await endListeningAndProcess();
    } else if (s.status === STATES.IDLE || s.status === STATES.SPEAKING) {
      if (voice.playing) voice.stopPlaying();
      await beginListening();
    }
  }

  // ── Hold orb 2s to toggle follow-up mode ──
  const holdTimerRef = useRef(null);
  const onOrbDown = () => {
    holdTimerRef.current = setTimeout(() => {
      const next = !s.followUp;
      dispatch({ type: "set", payload: { followUp: next } });
      voice.playAudio(next ? "Follow-up mode on. Let's keep talking."
                           : "Follow-up off.");
    }, 2000);
  };
  const onOrbUp = () => clearTimeout(holdTimerRef.current);

  // ── CONFIRMING handlers (yes/no via voice) ──
  useEffect(() => {
    if (s.status !== STATES.CONFIRMING) return;
    // After speaking the confirmation prompt, listen for yes/no
    const t = setTimeout(async () => {
      await beginListening();
      // Wait for user to stop on their own; reuse pipeline.
    }, 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line
  }, [s.status]);

  // Detect yes/no out of last user transcript when in CONFIRMING
  useEffect(() => {
    if (s.status !== STATES.PROCESSING || !api.pendingAction) return;
    const t = (s.lastUser || "").toLowerCase();
    if (!t) return;
    const yes = /(yes|yeah|sure|go|do it|please|haan|seri|sari)/.test(t);
    const no  = /(no|nope|cancel|stop|skip|don't|wait)/.test(t);
    if (yes || no) {
      api.confirmAction(api.pendingAction.action_id, yes).then(async (r) => {
        await speak(yes ? `Done. ${r.result || ''}`.slice(0, 240)
                        : "Okay, cancelled.");
      });
    }
    // eslint-disable-next-line
  }, [s.lastUser]);

  const status = s.status;
  const orbState = (
    status === STATES.LISTENING ? "listening" :
    status === STATES.THINKING || status === STATES.PROCESSING ? "thinking" :
    status === STATES.SPEAKING ? "speaking" :
    status === STATES.CONFIRMING ? "confirming" :
    status === STATES.ERROR ? "error" : "idle"
  );

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center text-white"
         style={{
           background:
             "radial-gradient(circle at 50% 30%, rgba(124,58,237,0.18), transparent 60%), #04060d",
         }}>
      {/* Startup overlay */}
      <AnimatePresence>
        {status === STATES.STARTUP && (
          <motion.div
            className="absolute inset-0 bg-black flex items-center justify-center text-violet-300 text-sm tracking-[0.5em]"
            initial={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.6 }}>
            BOOTING {profile.jarvisName?.toUpperCase()}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Hex grid backdrop */}
      <motion.div className="absolute inset-0 pointer-events-none"
        initial={{ opacity: 0 }} animate={{ opacity: 0.07 }} transition={{ delay: 1.2 }}
        style={{
          backgroundImage:
            "linear-gradient(60deg, rgba(167,139,250,0.4) 0 1px, transparent 1px 60px), linear-gradient(-60deg, rgba(167,139,250,0.4) 0 1px, transparent 1px 60px)",
          backgroundSize: "60px 60px",
        }} />

      <motion.div initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }} transition={{ delay: 1.5, duration: 0.8 }}
        className="flex flex-col items-center gap-4">
        {s.showAvatar && (
          <Avatar state={orbState} audioAmplitude={voice.amplitude} size={170}
                  emotion={status === STATES.SPEAKING ? "happy" : "neutral"} />
        )}
        <div onClick={onOrbTap}
             onMouseDown={onOrbDown} onMouseUp={onOrbUp}
             onTouchStart={onOrbDown} onTouchEnd={onOrbUp}
             className="cursor-pointer">
          <Orb state={orbState}
               audioAmplitude={voice.amplitude}
               audioFrequencies={voice.frequencies}
               size={300}
               name={profile.jarvisName} />
        </div>
        <div className="text-violet-200/70 text-xs tracking-widest">
          {status === STATES.IDLE && "TAP THE ORB OR SAY \"HEY JARVIS\""}
          {status === STATES.LISTENING && "LISTENING — TAP AGAIN TO STOP"}
          {status === STATES.PROCESSING && "PROCESSING…"}
          {status === STATES.THINKING && "THINKING…"}
          {status === STATES.SPEAKING && "SPEAKING…"}
          {status === STATES.CONFIRMING && "AWAITING CONFIRMATION (SAY YES OR NO)"}
        </div>
      </motion.div>

      {/* Live transcript pane (small, optional reading) */}
      <motion.div className="absolute bottom-4 left-4 right-4 max-h-44 overflow-auto
                              text-xs font-mono text-white/60 bg-black/40 border border-white/10
                              rounded-lg p-3 pointer-events-none"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 2.5 }}>
        {s.transcript.slice(-5).map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-emerald-300" : "text-violet-200"}>
            <span className="opacity-50">{m.role === "user" ? `${profile.userName}:` : `${profile.jarvisName}:`}</span> {m.text}
          </div>
        ))}
      </motion.div>

      {/* Floating upload zone (top-right) */}
      <div className="absolute top-2 right-2">
        <UploadBar
          onAnalysis={async (result) => {
            if (result?.spoken) await speak(result.spoken);
            else if (result?.analysis) await speak(result.analysis.slice(0, 600));
          }}
        />
      </div>

      {/* End-listening tap-anywhere */}
      {status === STATES.LISTENING && (
        <div className="absolute inset-0 cursor-pointer"
             onClick={endListeningAndProcess} />
      )}
    </div>
  );
}
