import { useEffect, useRef, useState } from 'react'
import { Settings } from 'lucide-react'
import { saveColumnPrefs } from '../../api/collection'
import type { ColumnVisibility } from '../../types'

interface Props {
  page: string
  columns: { key: string; label: string }[]
  visibility: ColumnVisibility
  onChange: (v: ColumnVisibility) => void
}

export default function ColumnPicker({ page, columns, visibility, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const toggle = async (key: string) => {
    const next = { ...visibility, [key]: !visibility[key] }
    onChange(next)
    await saveColumnPrefs(page, next)
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition"
      >
        <Settings size={14} />
        Columns
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-30 bg-gray-900 border border-gray-700 rounded-xl shadow-xl w-56 p-3 max-h-96 overflow-y-auto">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2 px-1">Show / Hide Columns</p>
          {columns.map(({ key, label }) => (
            <label key={key} className="flex items-center gap-2 px-1 py-1.5 rounded hover:bg-gray-800 cursor-pointer">
              <input
                type="checkbox"
                checked={visibility[key] !== false}
                onChange={() => toggle(key)}
                className="w-3.5 h-3.5 rounded accent-brand-500"
              />
              <span className="text-sm text-gray-300">{label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
