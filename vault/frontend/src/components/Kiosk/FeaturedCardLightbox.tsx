import { useState } from 'react'
import { X } from 'lucide-react'
import { resolveImageUrl } from '../../api/client'
import type { KioskTradingCard } from '../../types'

interface Props {
  title: string
  items: KioskTradingCard[]
  loading: boolean
  error: string | null
  browseAll: () => Promise<KioskTradingCard[]>
}

// Mirrors FeaturedLightbox.tsx's structure, deliberately more minimal -
// no grade/condition/price shown to customers even for cards found via the
// Graded Cards section (that section filters on having a grade on file,
// it just doesn't display it).
export default function FeaturedCardLightbox({ title, items, loading, error, browseAll }: Props) {
  const [selected, setSelected] = useState<KioskTradingCard | null>(null)
  const [browsing, setBrowsing] = useState(false)
  const [browseItems, setBrowseItems] = useState<KioskTradingCard[] | null>(null)
  const [browseLoading, setBrowseLoading] = useState(false)

  const openBrowseAll = async () => {
    setBrowsing(true)
    if (browseItems === null) {
      setBrowseLoading(true)
      try {
        setBrowseItems(await browseAll())
      } catch {
        setBrowseItems([])
      } finally {
        setBrowseLoading(false)
      }
    }
  }

  const closeBrowseAll = () => {
    setBrowsing(false)
    setSelected(null)
  }

  const renderTile = (item: KioskTradingCard) => (
    <button
      key={item.id}
      type="button"
      onClick={() => setSelected(item)}
      className="text-left group"
    >
      {item.img ? (
        <img
          src={resolveImageUrl(item.img) ?? undefined}
          alt={`${item.name}${item.card_number ? ` #${item.card_number}` : ''}`}
          className="w-full aspect-[8/11] object-cover rounded-lg group-hover:ring-2 group-hover:ring-brand-500 transition"
        />
      ) : (
        <div className="w-full aspect-[8/11] bg-gray-800 rounded-lg flex items-center justify-center text-gray-500 text-xs text-center px-2 group-hover:ring-2 group-hover:ring-brand-500 transition">
          {item.name}
        </div>
      )}
    </button>
  )

  return (
    <section className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-lg">{title}</h2>
        {!loading && !error && items.length > 0 && (
          <button
            type="button"
            onClick={openBrowseAll}
            className="text-sm text-brand-400 hover:text-brand-300 transition"
          >
            Browse All
          </button>
        )}
      </div>
      {loading && <p className="text-gray-400 text-sm">Loading…</p>}
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-gray-500 text-sm italic">Nothing to show right now.</p>
      )}

      {items.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {items.map((item) => (
            <div key={item.id} className="flex-shrink-0 w-32">
              {renderTile(item)}
            </div>
          ))}
        </div>
      )}

      {browsing && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4"
          onClick={closeBrowseAll}
        >
          <div
            className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h3 className="font-semibold text-lg">{title} — Browse All</h3>
              <button onClick={closeBrowseAll} className="text-gray-400 hover:text-white transition">
                <X size={20} />
              </button>
            </div>
            <div className="overflow-y-auto p-6">
              {browseLoading ? (
                <p className="text-gray-400 text-sm">Loading…</p>
              ) : !browseItems || browseItems.length === 0 ? (
                <p className="text-gray-500 text-sm italic">Nothing to show right now.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  {browseItems.map((item) => renderTile(item))}
                </div>
              )}
            </div>
          </div>
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
                {selected.name}
                {selected.card_number && <span className="text-gray-400"> #{selected.card_number}</span>}
              </h3>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-white transition">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-3">
              {selected.img && (
                <img src={resolveImageUrl(selected.img) ?? undefined} alt="" className="w-full max-h-96 object-contain rounded-lg" />
              )}
              <p className="text-gray-400 text-sm">
                {[selected.game_name, selected.set_name].filter(Boolean).join(' · ')}
              </p>
              {selected.rarity && <p className="text-gray-400 text-sm">{selected.rarity}</p>}
              <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-full bg-green-900/50 text-green-400">
                {selected.available} available
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
