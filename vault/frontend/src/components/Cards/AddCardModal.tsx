import { useState } from 'react'
import { X, Search } from 'lucide-react'
import { searchCards, addCardToCollection } from '../../api/cards'
import type { TradingCard, UserTradingCard } from '../../types'

interface Props {
  onClose: () => void
  onAdded: (uc: UserTradingCard) => void
}

export default function AddCardModal({ onClose, onAdded }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TradingCard[]>([])
  const [searching, setSearching] = useState(false)
  const [selected, setSelected] = useState<TradingCard | null>(null)
  const [count, setCount] = useState('1')
  const [condition, setCondition] = useState('')
  const [paidPrice, setPaidPrice] = useState('')
  const [pointOfPurchase, setPointOfPurchase] = useState('')
  const [buyDate, setBuyDate] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const runSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    setError('')
    try {
      const cards = await searchCards({ name: query.trim(), limit: 25 })
      setResults(cards)
    } catch {
      setError('Search failed. Please try again.')
    } finally {
      setSearching(false)
    }
  }

  const handleAdd = async () => {
    if (!selected) return
    setSaving(true)
    setError('')
    try {
      const uc = await addCardToCollection({
        card_id: selected.id,
        count: count ? Number(count) : 1,
        condition: condition || undefined,
        paid_price: paidPrice ? Number(paidPrice) : undefined,
        point_of_purchase: pointOfPurchase || undefined,
        buy_date: buyDate || undefined,
        notes: notes || undefined,
      })
      onAdded(uc)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Failed to add card. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="font-semibold text-lg">Add Card to Collection</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1">
          {!selected ? (
            <>
              <div className="flex gap-2 mb-4">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && runSearch()}
                    placeholder="Search by card name…"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <button onClick={runSearch} className="bg-brand-500 hover:bg-brand-600 text-white font-medium px-5 py-2.5 rounded-lg transition">
                  Search
                </button>
              </div>

              {searching ? (
                <p className="text-center text-gray-400 py-8">Searching…</p>
              ) : results.length === 0 ? (
                <p className="text-center text-gray-500 text-sm py-8">
                  {query ? "No cards found. Ask an admin to sync the catalog for this game/set if it should be here." : 'Search for a card by name to get started.'}
                </p>
              ) : (
                <div className="space-y-2">
                  {results.map(card => (
                    <button
                      key={card.id}
                      onClick={() => setSelected(card)}
                      className="w-full flex items-center gap-3 bg-gray-800 hover:bg-gray-700 rounded-lg px-3 py-2 text-left transition"
                    >
                      {card.image_small && (
                        <img src={card.image_small} alt="" className="w-8 h-11 object-cover rounded border border-gray-700 flex-shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white truncate">{card.name}</p>
                        <p className="text-xs text-gray-400 truncate">
                          {[card.game_name, card.set_name, card.card_number && `#${card.card_number}`].filter(Boolean).join(' · ')}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="flex items-center gap-3 mb-6 bg-gray-800/60 rounded-lg px-3 py-2">
                {selected.image_small && (
                  <img src={selected.image_small} alt="" className="w-10 h-14 object-cover rounded border border-gray-700" />
                )}
                <div className="flex-1">
                  <p className="font-medium">{selected.name}</p>
                  <p className="text-xs text-gray-400">
                    {[selected.game_name, selected.set_name, selected.card_number && `#${selected.card_number}`].filter(Boolean).join(' · ')}
                  </p>
                </div>
                <button onClick={() => setSelected(null)} className="text-sm text-gray-400 hover:text-white transition">
                  Change
                </button>
              </div>

              <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">Your Details</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Count</label>
                  <input type="number" min="1" value={count} onChange={e => setCount(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Condition</label>
                  <input value={condition} onChange={e => setCondition(e.target.value)} placeholder="e.g. Near Mint" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Paid Price ($)</label>
                  <input type="number" min="0" step="0.01" value={paidPrice} onChange={e => setPaidPrice(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Point of Purchase</label>
                  <input value={pointOfPurchase} onChange={e => setPointOfPurchase(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Buy Date</label>
                  <input type="date" value={buyDate} onChange={e => setBuyDate(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm text-gray-400 mb-1">Notes</label>
                  <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
                </div>
              </div>
            </>
          )}
        </div>

        {error && <p className="px-6 text-red-400 text-sm">{error}</p>}

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition">
            Cancel
          </button>
          {selected && (
            <button
              onClick={handleAdd}
              disabled={saving}
              className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
            >
              {saving ? 'Adding…' : 'Add to Collection'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
