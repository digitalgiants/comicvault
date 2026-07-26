import { useState } from 'react'
import { X } from 'lucide-react'
import type { KioskCard } from '../../types'

interface Props {
  title: string
  items: KioskCard[]
  loading: boolean
  error: string | null
}

export default function FeaturedLightbox({ title, items, loading, error }: Props) {
  const [selected, setSelected] = useState<KioskCard | null>(null)

  return (
    <section className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
      <h2 className="font-semibold text-lg mb-4">{title}</h2>
      {loading && <p className="text-gray-400 text-sm">Loading…</p>}
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-gray-500 text-sm italic">Nothing to show right now.</p>
      )}

      {items.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelected(item)}
              className="flex-shrink-0 w-32 text-left group"
            >
              {item.img ? (
                <img
                  src={item.img}
                  alt={`${item.series ?? 'Unknown series'} #${item.issue_number ?? '?'}`}
                  className="w-32 h-48 object-cover rounded-lg group-hover:ring-2 group-hover:ring-brand-500 transition"
                />
              ) : (
                <div className="w-32 h-48 bg-gray-800 rounded-lg flex items-center justify-center text-gray-500 text-xs text-center px-2 group-hover:ring-2 group-hover:ring-brand-500 transition">
                  {item.series} #{item.issue_number}
                </div>
              )}
              {item.average_price != null && (
                <div className="text-green-400 text-sm mt-1">${item.average_price.toFixed(2)}</div>
              )}
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h3 className="font-semibold text-lg">
                {selected.series} #{selected.issue_number}
                {selected.variant && <span className="text-gray-400"> ({selected.variant})</span>}
              </h3>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-white transition">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-3">
              {selected.img && (
                <img src={selected.img} alt="" className="w-full max-h-96 object-contain rounded-lg" />
              )}
              <p className="text-gray-400 text-sm">
                {[selected.publisher, selected.volume ? `Vol. ${selected.volume}` : null]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              {selected.cover_date && <p className="text-gray-400 text-sm">{selected.cover_date}</p>}
              {selected.condition && <p className="text-gray-300 text-sm">Condition: {selected.condition}</p>}
              {selected.average_price != null && (
                <p className="text-green-400 font-medium">${selected.average_price.toFixed(2)}</p>
              )}
              <div className="flex flex-wrap gap-2">
                {selected.signed && (
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400">Signed</span>
                )}
                {selected.remarked && (
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400">Remarked</span>
                )}
                {selected.direct !== null && (
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-700 text-gray-300">
                    {selected.direct ? 'Direct' : 'Newsstand'}
                  </span>
                )}
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-green-900/50 text-green-400">
                  {selected.available} available
                </span>
              </div>
              <div className="text-sm text-gray-400 space-y-0.5">
                {selected.writer && <p>Writer: {selected.writer}</p>}
                {selected.penciller && <p>Pencils: {selected.penciller}</p>}
                {selected.inker && <p>Inks: {selected.inker}</p>}
                {selected.cover_artist && <p>Cover: {selected.cover_artist}</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
