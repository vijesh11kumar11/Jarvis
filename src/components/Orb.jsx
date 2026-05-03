import React, { useEffect, useRef, useMemo } from "react";

/*
 * Friday's holographic particle orb.
 * 200 particles distributed on a sphere, projected to 2D each frame.
 * State drives color, glow, and rotation speed.
 *
 * Props:
 *   state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'confirming' | 'error'
 *   audioAmplitude: 0..1
 *   audioFrequencies: Float32Array (optional, 64 bins)
 *   size: px
 *   name: label below the orb
 */
const STATE_COLORS = {
  idle:       { core: "#7C3AED", glow: "rgba(124, 58, 237, 0.45)", ring: "#A78BFA" },
  listening:  { core: "#10B981", glow: "rgba(16, 185, 129, 0.55)", ring: "#34D399" },
  thinking:   { core: "#3B82F6", glow: "rgba(59, 130, 246, 0.5)",  ring: "#60A5FA" },
  speaking:   { core: "#8B5CF6", glow: "rgba(139, 92, 246, 0.6)",  ring: "#C4B5FD" },
  confirming: { core: "#F59E0B", glow: "rgba(245, 158, 11, 0.55)", ring: "#FCD34D" },
  error:      { core: "#EF4444", glow: "rgba(239, 68, 68, 0.55)",  ring: "#FCA5A5" },
};

function buildParticles(count, radius) {
  const arr = [];
  for (let i = 0; i < count; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    arr.push({
      theta, phi,
      baseSpeed: 0.0015 + Math.random() * 0.004,
      size: 1 + Math.random() * 1.8,
      radius,
    });
  }
  return arr;
}

export default function Orb({
  state = "idle",
  audioAmplitude = 0,
  audioFrequencies = null,
  size = 300,
  name = "Friday",
}) {
  const canvasRef = useRef(null);
  const rafRef = useRef(0);
  const colors = STATE_COLORS[state] || STATE_COLORS.idle;
  const radius = size * 0.36;

  const particles = useMemo(() => buildParticles(200, radius), [radius]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);
    const cx = size / 2, cy = size / 2;

    const render = () => {
      ctx.clearRect(0, 0, size, size);

      // Glow
      const speedMult = 1 + audioAmplitude * 4;
      const glowR = radius * (1.4 + audioAmplitude * 0.6);
      const grad = ctx.createRadialGradient(cx, cy, radius * 0.1, cx, cy, glowR);
      grad.addColorStop(0, colors.glow);
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(cx, cy, glowR, 0, Math.PI * 2); ctx.fill();

      // Particles
      for (const p of particles) {
        p.theta += p.baseSpeed * speedMult;
        const x3 = p.radius * Math.sin(p.phi) * Math.cos(p.theta);
        const y3 = p.radius * Math.sin(p.phi) * Math.sin(p.theta);
        const z3 = p.radius * Math.cos(p.phi);
        const x2 = cx + x3;
        const y2 = cy + y3 * 0.7;
        const depth = (z3 / p.radius + 1) / 2; // 0..1
        const opacity = 0.25 + depth * 0.75;
        ctx.fillStyle = colors.core + Math.round(opacity * 255).toString(16).padStart(2, "0");
        ctx.beginPath();
        ctx.arc(x2, y2, p.size * (0.6 + depth * 0.6), 0, Math.PI * 2);
        ctx.fill();
      }

      // Audio waveform ring (when listening / speaking)
      if ((state === "listening" || state === "speaking") && audioFrequencies && audioFrequencies.length) {
        const ringR = radius * 1.05;
        ctx.strokeStyle = colors.ring;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        const points = 64;
        for (let i = 0; i < points; i++) {
          const a = (i / points) * Math.PI * 2;
          const f = audioFrequencies[i % audioFrequencies.length] || 0;
          const r = ringR + f * 14;
          const x = cx + Math.cos(a) * r;
          const y = cy + Math.sin(a) * r * 0.92;
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.closePath(); ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(render);
    };
    rafRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(rafRef.current);
  }, [size, colors, radius, particles, state, audioAmplitude, audioFrequencies]);

  return (
    <div className="relative flex flex-col items-center justify-center select-none"
         style={{ width: size, height: size + 32 }}>
      <canvas ref={canvasRef}
              style={{ width: size, height: size }}
              className="block" />
      {/* SVG ring overlay */}
      <svg className="absolute top-0 left-0 pointer-events-none"
           width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={radius * 1.18}
                fill="none" stroke={colors.ring} strokeOpacity="0.35"
                strokeWidth="1" strokeDasharray="3 6" />
        <circle cx={size / 2} cy={size / 2} r={radius * 1.32}
                fill="none" stroke={colors.ring} strokeOpacity="0.18"
                strokeWidth="1" />
      </svg>
      <div className="mt-2 text-xs uppercase tracking-[0.3em]"
           style={{ color: colors.ring, opacity: 0.85 }}>
        {name} · {state}
      </div>
    </div>
  );
}
