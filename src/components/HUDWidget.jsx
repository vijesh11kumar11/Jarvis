import React from 'react'

export default function HUDWidget({ title, children, className = '' }) {
  return (
    <div className={`hud-border rounded-md p-3 ${className}`}>
      <div className="text-[9px] tracking-[0.35em] text-cyan-400/70 uppercase mb-2">
        {title}
      </div>
      <div className="text-gray-300 text-sm">{children}</div>
    </div>
  )
}
