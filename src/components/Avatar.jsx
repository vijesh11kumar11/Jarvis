import React, { useEffect, useMemo, useState } from "react";
import { motion, useAnimation } from "framer-motion";

/*
 * Friday's holographic SVG avatar.
 * Hexagonal head, almond eyes, geometric cheekbones, thin lip mouth.
 * Reactive to state + audio amplitude. All strokes ~70% opacity.
 *
 * Props:
 *   state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'confirming'
 *   audioAmplitude: 0..1
 *   emotion: 'neutral' | 'happy' | 'focused' | 'curious'
 *   size: px
 */
const PALETTE = {
  idle:       "#7C3AED",
  listening:  "#10B981",
  thinking:   "#3B82F6",
  speaking:   "#8B5CF6",
  confirming: "#F59E0B",
};

export default function Avatar({
  state = "idle",
  audioAmplitude = 0,
  emotion = "neutral",
  size = 200,
}) {
  const stroke = PALETTE[state] || PALETTE.idle;
  const ctrl = useAnimation();

  // Random blink loop
  const [blinking, setBlinking] = useState(false);
  useEffect(() => {
    let t;
    const loop = () => {
      const wait = 3000 + Math.random() * 4000;
      t = setTimeout(() => {
        setBlinking(true);
        setTimeout(() => setBlinking(false), 130);
        loop();
      }, wait);
    };
    loop();
    return () => clearTimeout(t);
  }, []);

  // Breathing
  useEffect(() => {
    ctrl.start({
      scale: [1, 1.02, 1],
      transition: { duration: 4, repeat: Infinity, ease: "easeInOut" },
    });
  }, [ctrl]);

  // Mouth open amount tracks audio amplitude when speaking.
  const openAmount = state === "speaking" ? 2 + audioAmplitude * 18 : 2;
  const mouthPath = useMemo(() => (
    `M 70 130 Q 100 ${130 + openAmount} 130 130 Q 100 ${130 - openAmount * 0.3} 70 130`
  ), [openAmount]);

  // State-driven adjustments
  const eyeScaleY = blinking ? 0.05 : (state === "listening" ? 1.15 : 1);
  const browY = state === "listening" ? -3 : state === "thinking" ? -1 : 0;
  const browSkew = state === "thinking" ? 6 : 0;
  const headTilt = state === "listening" ? 3 : 0;
  const eyeOffsetX = state === "thinking" ? -3 : 0;
  const eyeOffsetY = state === "thinking" ? -3 : 0;
  const happyCurve = emotion === "happy" ? 6 : 0;

  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      animate={ctrl}
      style={{ transform: `rotate(${headTilt}deg)`, transition: "transform 0.5s ease" }}
    >
      <defs>
        <linearGradient id="holo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.95" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0.45" />
        </linearGradient>
      </defs>

      {/* Head: rounded hexagon */}
      <polygon
        points="100,18 168,55 168,140 100,182 32,140 32,55"
        fill="none"
        stroke="url(#holo)"
        strokeWidth="1.6"
        strokeOpacity="0.7"
      />

      {/* Cheekbone lines */}
      <line x1="50" y1="115" x2="80" y2="125" stroke={stroke} strokeWidth="1" strokeOpacity="0.4" />
      <line x1="150" y1="115" x2="120" y2="125" stroke={stroke} strokeWidth="1" strokeOpacity="0.4" />

      {/* Brows */}
      <line x1="60"  y1={75 + browY} x2={88 + browSkew} y2={70 + browY} stroke={stroke} strokeWidth="2" strokeOpacity="0.7" />
      <line x1="140" y1={75 + browY} x2={112 - browSkew} y2={70 + browY} stroke={stroke} strokeWidth="2" strokeOpacity="0.7" />

      {/* Eyes (almond) */}
      <g transform={`translate(${eyeOffsetX} ${eyeOffsetY})`}>
        <ellipse cx="74" cy="95" rx="10" ry={9 * eyeScaleY}
                 fill={stroke} fillOpacity="0.18"
                 stroke={stroke} strokeOpacity="0.7" strokeWidth="1.4" />
        <ellipse cx="126" cy="95" rx="10" ry={9 * eyeScaleY}
                 fill={stroke} fillOpacity="0.18"
                 stroke={stroke} strokeOpacity="0.7" strokeWidth="1.4" />
        {!blinking && (
          <>
            <circle cx="74" cy="95" r="2.4" fill={stroke} />
            <circle cx="126" cy="95" r="2.4" fill={stroke} />
          </>
        )}
      </g>

      {/* Mouth (audio-reactive when speaking) */}
      <path
        d={emotion === "happy"
          ? `M 70 130 Q 100 ${130 + happyCurve + openAmount * 0.5} 130 130`
          : mouthPath}
        fill="none"
        stroke={stroke}
        strokeOpacity="0.85"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* Scan line when thinking */}
      {state === "thinking" && (
        <motion.line
          x1="40" x2="160"
          stroke={stroke}
          strokeOpacity="0.5"
          strokeWidth="1"
          strokeDasharray="2 4"
          initial={{ y1: 60, y2: 60 }}
          animate={{ y1: [60, 150, 60], y2: [60, 150, 60] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
    </motion.svg>
  );
}
