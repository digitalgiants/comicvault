import { useState } from 'react'
import { X } from 'lucide-react'
import type { StagedItem } from '../../types'

interface Props {
  items: StagedItem[]
  maxItems: number
  submitting: boolean
  error: string | null
  onAddPasted: (codes: { upc12: string; ean5: string | null }[]) => void
  onRemove: (id: string) => void
  onEdit: (id: string, upc12: string, ean5: string | null) => void
  onSubmit: () => void
}

function parseLines(text: string): { upc12: string; ean5: string | null }[] {
  return text
    .split('\n')
    .map((line) => line.replace(/\D/g, ''))
    .filter((digits) => digits.length === 12 || digits.length === 17)
    .map((digits) =>
      digits.length === 17
        ? { upc12: digits.slice(0, 12), ean5: digits.slice(12) }
        : { upc12: digits, ean5: null },
    )
}

export default function BatchPanel({
  items,
  maxItems,
  submitting,
  error,
  onAddPasted,
  onRemove,
  onEdit,
  onSubmit,
}: Props) {
  const [pasteText, setPasteText] = useState('')
  const atLimit = items.length >= maxItems

  function handlePasteSubmit(e: React.FormEvent) {
    e.preventDefault()
    onAddPasted(parseLines(pasteText))
    setPasteText('')
  }

  return (
    <div className="bg-gray-900 rounded-2xl p-5 border border-gray-800 space-y-4">
      <p className="text-xs text-gray-500">
        Batches are limited to {maxItems} items — Metron currently only supports 20 requests/minute,
        so large or uncached batches take a bit to fully process.
      </p>

      <form className="flex flex-col sm:flex-row gap-2" onSubmit={handlePasteSubmit}>
        <textarea
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          placeholder="Paste UPCs, one per line (12 or 17 digits each)"
          rows={3}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
        />
        <button
          type="submit"
          disabled={!pasteText.trim() || atLimit}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition disabled:opacity-50 self-start"
        >
          Add to batch
        </button>
      </form>

      {atLimit && (
        <p className="text-yellow-400 text-sm">
          Batch is full ({maxItems} items) — submit or remove some before adding more.
        </p>
      )}

      {items.length > 0 && (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.id} className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2">
              <input
                value={item.upc12}
                onChange={(e) => onEdit(item.id, e.target.value.replace(/\D/g, ''), item.ean5)}
                inputMode="numeric"
                pattern="\d*"
                aria-label="UPC"
                className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <input
                value={item.ean5 ?? ''}
                onChange={(e) => onEdit(item.id, item.upc12, e.target.value.replace(/\D/g, '') || null)}
                placeholder="EAN-5"
                inputMode="numeric"
                pattern="\d*"
                aria-label="EAN-5"
                className="w-28 bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                type="button"
                onClick={() => onRemove(item.id)}
                aria-label="Remove from batch"
                className="p-1 text-gray-500 hover:text-red-400 transition"
              >
                <X size={16} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        type="button"
        onClick={onSubmit}
        disabled={items.length === 0 || submitting}
        className="w-full px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
      >
        {submitting ? 'Submitting…' : `Look up ${items.length} item${items.length === 1 ? '' : 's'}`}
      </button>
    </div>
  )
}
