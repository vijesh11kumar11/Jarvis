/* src/pages/JarvisChat.jsx
 * Voice-only conversation surface for Friday.
 * Startup sequence → idle → wake → listen → think → speak → idle.
 * Tap-to-talk + push-to-hold + auto wake-word + double-clap.
 * Avatar + Orb both react to amplitude.
 *
 * BUGS FIXED:
 *  1. Stale closures — all volatile state referenced inside async funcs
 *     goes through refs, not the reducer snapshot.
 *  2. CONFIRMING flow — confirmingRef short-circuits endListeningAndProcess
 *     into a yes/no path instead of a normal chat round.
 *  3. Transcript accumulation — uses functional dispatch reducer so
 *     consecutive dispatches never clobber each other.
 *  4. Wake-word SSE — reads statusRef so it never acts on stale status.
 */
import React, { useEffect, useReducer, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Orb from "../components/Orb.jsx";
import Avatar from "../components/Avatar.jsx";
import UploadBar from "../components/UploadBar.jsx";
import { useVoice } from "../hooks/useVoice.js";
import { useJarvisAPI } from "../hooks/useJarvis.js";
import { useJarvis } from "../context/JarvisContext.jsx";

const S = {
  STARTUP:    "STARTUP",
  IDLE:       "IDLE",
  LISTENING:  "LISTENING",
  PROCESSING: "PROCESSING",
  THINKING:   "THINKING",
  SPEAKING:   "SPEAKING",
  CONFIRMING: "CONFIRMING",
  ERROR:      "ERROR",
};

function reducer(state, action) {
  switch (action.type) {
    case "status":     return { ...state, status: action.payload };
    case "followUp":   return { ...state, followUp: action.payload };
    case "pushMsg":    return { ...state,
                         transcript: [...state.transcript, action.payload].slice(-30) };
    case "lastUser":   return { ...state, lastUser: action.payload };
    case "lastAssist": return { ...state, lastAssistant: action.payload };
    default:           return state;
  }
}

export default function JarvisChat() {
  const { profile } = useJarvis();
  const userId = profile?.userId || "anonymous";

  const [s, dispatch] = useReducer(reducer, {
    status:         S.STARTUP,
    lastUser:       "",
    lastAssistant:  "",
    transcript:     [],
    followUp:       false,
    showAvatar:     localStorage.getItem("jarvis_show_avatar") !== "false",
  });

  // ── Refs so async funcs always see current values ──
  const statusRef     = useRef(S.STARTUP);
  const followUpRef   = useRef(false);
  const confirmingRef = useRef(false);   // true while we wait for yes/no
  const pendingRef    = useRef(null);    // holds api.pendingAction during confirmation
  const briefedRef    = useRef(false);

  const setStatus = (st) => {
    statusRef.current = st;
    dispatch({ type: "status", payload: st });
  };

  const voice = useVoice();
  const api   = useJarvisAPI({ userId,
    jarvisName: profile.jarvisName,
    userName:   profile.userName });

  // ── Startup ──
  useEffect(() => {
    const t = setTimeout(() => setStatus(S.IDLE), 2500);
    return () => clearTimeout(t);
  }, []);

  // ── Morning briefing — fires once when first IDLE ──
  useEffect(() => {
    if (s.status !== S.IDLE || briefedRef.current) return;
    briefedRef.current = true;
    (async () => {
      try {
        if (userId === "anonymous") {
          await speak(`Hey ${profile.userName}, I'm ${profile.jarvisName}. Tap the orb whenever you want to talk.`);
          return;
        }
        const brief = await api.triggerMorningBriefing();
        if (brief?.spoken) await speak(brief.spoken);
      } catch (e) { console.warn("[chat] briefing skipped", e); }
    })();
    // eslint-disable-next-line
  }, [s.status]);

  // ── Wake-word SSE (reads statusRef — never stale) ──
  useEffect(() => {
    fetch("http://localhost:8000/wake-word/start", { method: "POST" }).catch(() => {});
    const sse = new EventSource("http://localhost:8000/wake-word/events");
    sse.onmessage = () => {
      const st = statusRef.current;
      if (st === S.IDLE || st === S.SPEAKING) {
        if (voice.playing) voice.stopPlaying();
        beginListening();
      }
    };
    sse.onerror = () => {};
    return () => sse.close();
    // eslint-disable-next-line
  }, []);  // mount-only; reads refs not state

  // ── Core: speak text, then auto-listen or go idle ──
  async function speak(text, thenListen = false) {
    if (!text) { setStatus(S.IDLE); return; }
    setStatus(S.SPEAKING);
    await new Promise((resolve) => {
      voice.playAudio(text, profile?.voiceId, () => {
        if (thenListen || followUpRef.current) {
          beginListening();
        } else {
          setStatus(S.IDLE);
        }
        resolve();
      });
    });
  }

  async function beginListening() {
    setStatus(S.LISTENING);
    await voice.startListening();
  }

  // ── Main pipeline: stop mic → transcribe → chat → speak ──
  async function endListeningAndProcess() {
    setStatus(S.PROCESSING);
    const result = await voice.stopListening();
    const text   = (result?.text || "").trim();
    if (!text) { setStatus(S.IDLE); return; }

    dispatch({ type: "lastUser",  payload: text });
    dispatch({ type: "pushMsg",   payload: { role: "user", text } });

    // ── CONFIRMING path: we're waiting for yes / no ──
    if (confirmingRef.current && pendingRef.current) {
      const tl   = text.toLowerCase();
      const yes  = /(yes|yeah|sure|go|do it|please|haan|seri|sari|ok|okay)/.test(tl);
      const no   = /(no|nope|cancel|stop|skip|wait|don't|illa|venda)/.test(tl);
      if (yes || no) {
        confirmingRef.current = false;        // clear only on valid yes/no
        setStatus(S.THINKING);
        try {
          const actionId = pendingRef.current.action_id;
          const r = await api.confirmAction(actionId, yes);
          pendingRef.current = null;           // clear only after confirmAction completes
          const reply = yes
            ? `Done. ${r?.result || "Action completed."}`.slice(0, 240)
            : "Got it, cancelled that.";
          dispatch({ type: "pushMsg",    payload: { role: "assistant", text: reply } });
          dispatch({ type: "lastAssist", payload: reply });
          await speak(reply);
        } catch (e) {
          await speak("Hmm, something went wrong with that action.");
        }
      } else {
        // Stay in confirming mode — confirmingRef remains true
        await speak("Just say yes or no — should I go ahead?", true);
      }
      return;
    }

    // ── Normal chat path ──
    setStatus(S.THINKING);
    let gotReply = false;
    await api.chat(text, {
      onDelta: () => {},
      onDone: async (full, obj) => {
        gotReply = true;
        dispatch({ type: "lastAssist", payload: full });
        dispatch({ type: "pushMsg",    payload: { role: "assistant", text: full } });

        if (api.pendingAction) {
          // Confirmation needed (send_whatsapp / send_email etc.)
          pendingRef.current    = api.pendingAction;
          confirmingRef.current = true;
          const q = api.pendingAction.speak ||
            "I'd like to take an action for you — say yes to confirm or no to cancel.";
          await speak(q, true);
        } else if (obj?.action_executed) {
          // Auto-executed action (open_website / screenshot etc.) — just speak confirmation
          const spokenText = obj.action_executed.speak || full;
          await speak(spokenText);
        } else {
          await speak(full);
        }
      },
      onError: async (err) => {
        gotReply = true;
        await speak(`Something broke: ${err}`);
      },
    });
    if (!gotReply) setStatus(S.IDLE);
  }

  // ── Tap orb ──
  async function onOrbTap() {
    const st = statusRef.current;
    if (st === S.LISTENING) {
      await endListeningAndProcess();
    } else if (st === S.IDLE || st === S.SPEAKING) {
      if (voice.playing) voice.stopPlaying();
      await beginListening();
    }
  }

  // ── Hold orb 2 s → toggle follow-up (conversation) mode ──
  const holdRef = useRef(null);
  const onOrbDown = () => {
    holdRef.current = setTimeout(() => {
      const next = !followUpRef.current;
      followUpRef.current = next;
      dispatch({ type: "followUp", payload: next });
      voice.playAudio(next
        ? "Follow-up mode on — I'll keep listening after each reply."
        : "Follow-up mode off.");
    }, 2000);
  };
  const onOrbUp = () => clearTimeout(holdRef.current);

  const status = s.status;
  const orbState = (
    status === S.LISTENING  ? "listening" :
    status === S.THINKING || status === S.PROCESSING ? "thinking" :
    status === S.SPEAKING   ? "speaking"  :
    status === S.CONFIRMING ? "confirming" :
    status === S.ERROR      ? "error" : "idle"
  );

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center text-white"
         style={{
           background:
             "radial-gradient(circle at 50% 30%, rgba(124,58,237,0.18), transparent 60%), #04060d",
         }}>
      {/* Startup overlay */}
      <AnimatePresence>
        {status === S.STARTUP && (
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
                  emotion={status === S.SPEAKING ? "happy" : "neutral"} />
        )}
        <div onClick={onOrbTap}
             onMouseDown={onOrbDown} onMouseUp={onOrbUp}
             onTouchStart={onOrbDown} onTouchEnd={onOrbUp}
             className="cursor-pointer select-none">
          <Orb state={orbState}
               audioAmplitude={voice.amplitude}
               audioFrequencies={voice.frequencies}
               size={300}
               name={profile.jarvisName} />
        </div>
        <div className="text-violet-200/70 text-xs tracking-widest">
          {status === S.IDLE       && "TAP THE ORB OR SAY \"HEY JARVIS\""}
          {status === S.LISTENING  && "LISTENING — TAP AGAIN TO SEND"}
          {status === S.PROCESSING && "PROCESSING…"}
          {status === S.THINKING   && "THINKING…"}
          {status === S.SPEAKING   && "SPEAKING…"}
          {status === S.CONFIRMING && "SAY YES OR NO"}
        </div>
        {s.followUp && (
          <div className="text-emerald-400/70 text-[10px] tracking-widest">
            ● CONVERSATION MODE — HOLD ORB TO STOP
          </div>
        )}
      </motion.div>

      {/* Live transcript pane */}
      <motion.div className="absolute bottom-4 left-4 right-4 max-h-44 overflow-auto
                              text-xs font-mono text-white/60 bg-black/40 border border-white/10
                              rounded-lg p-3 pointer-events-none"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 2.5 }}>
        {s.transcript.slice(-6).map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-emerald-300" : "text-violet-200"}>
            <span className="opacity-50">
              {m.role === "user" ? `${profile.userName}:` : `${profile.jarvisName}:`}
            </span>{" "}{m.text}
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

      {/* Tap-anywhere-to-send while listening */}
      {status === S.LISTENING && (
        <div className="absolute inset-0 cursor-pointer z-10"
             onClick={endListeningAndProcess} />
      )}
    </div>
  );
}
