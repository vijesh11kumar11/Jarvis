import React from 'react'
import { Link, useLocation } from 'react-router-dom'

const items = [
  { to: '/', icon: '◉', label: 'Friday' },
  { to: '/insights', icon: '▤', label: 'Market' },
  { to: '/about-me', icon: '☻', label: 'About Me' },
  { to: '/settings', icon: '⚙', label: 'Settings' },
]

export default function Sidebar() {
  const loc = useLocation()
  return (
    <div className="w-14 bg-black/60 border-r border-violet-900/30 flex flex-col items-center py-4 gap-3">
      {items.map(it => (
        <Link key={it.to} to={it.to} title={it.label}
          className={`w-10 h-10 rounded-md flex items-center justify-center text-xl titlebar-no-drag ${loc.pathname === it.to ? 'bg-violet-700/30 text-violet-200' : 'text-gray-500 hover:text-violet-300'}`}>
          {it.icon}
        </Link>
      ))}
    </div>
  )
}
