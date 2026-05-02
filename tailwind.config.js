/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg: '#000000',
          panel: '#0a0a12',
          ring: '#7C3AED',
          listen: '#10B981',
          think: '#3B82F6',
          speak: '#A78BFA',
          dim: '#6B7280',
          hud: '#22D3EE',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        display: ['Orbitron', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        breathe: {
          '0%,100%': { transform: 'scale(1)', filter: 'brightness(1)' },
          '50%': { transform: 'scale(1.05)', filter: 'brightness(1.3)' },
        },
        ripple: {
          '0%': { transform: 'scale(1)', opacity: 1 },
          '100%': { transform: 'scale(1.6)', opacity: 0 },
        },
        scan: {
          '0%': { top: '0%' },
          '100%': { top: '100%' },
        },
        spinslow: { to: { transform: 'rotate(360deg)' } },
        spinrev: { to: { transform: 'rotate(-360deg)' } },
        orbit: { to: { transform: 'rotate(360deg)' } },
      },
      animation: {
        breathe: 'breathe 3s ease-in-out infinite',
        ripple: 'ripple 1.2s ease-out infinite',
        scan: 'scan 8s linear infinite',
        spinslow: 'spinslow 16s linear infinite',
        spinrev: 'spinrev 24s linear infinite',
      },
    },
  },
  plugins: [],
}
