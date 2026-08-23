import { useEffect, useState, useCallback } from 'react'
import { Search, Pencil, DollarSign, Trash2, ChevronLeft, ChevronRight, Plus, ScanLine } from 'lucide-react'
import { getCardCollection, recordCardSale, deleteUserTradingCard, getCardColumnPrefs } from '../api/cards'
import { resolveImageUrl } from '../api/client'
import { availableCardCopies, cardCoverImage, latestCardSalePrice, type UserTradingCard, type ColumnVisibility, visibleCardsColumns } from '../types'
import { useAuth } from '../hooks/useAuth'
import EditTradingCardModal from '../components/Cards/EditTradingCardModal'
import RecordCardSaleModal from '../components/Cards/RecordCardSaleModal'
import AddCardModal from '../components/Cards/AddCardModal'
import CardScanModal from '../components/Cards/CardScanModal'
import ColumnPicker from '../components/Collection/ColumnPicker'

const PAGE_SIZE = 200

export default function CardsPage() {
  const { user } = useAuth()
  const isCollector = !!user?.is_collector
  const [items, setItems] = useState<UserTradingCard[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<UserTradingCard | null>(null)
  const [selling, setSelling] = useState<UserTradingCard | null>(null)
  const [adding, setAdding] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [visibility, setVisibility] = useState<ColumnVisibility>({})

  useEffect(() => {
    getCardColumnPrefs('cards').then(p => setVisibility(p.columns))
  }, [])

  const fetchCollection = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = {
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }
      if (search) params.name = search
      const { items, total } = await getCardCollection(params)
      setItems(items)
      setTotal(total)
    } catch {
      setError('Failed to load your cards. Your collection is safe — this is a loading error, please try again.')
    } finally {
      setLoading(false)
    }
  }, [search, page])

  useEffect(() => { fetchCollection() }, [page])

  const runSearch = () => {
    if (page === 1) fetchCollection()
    else setPage(1)
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const columns = visibleCardsColumns(isCollector)
  const visibleCols = columns.filter(c => visibility[c.key] !== false)

  const handleDelete = async (uc: UserTradingCard) => {
    if (!confirm(`Permanently delete "${uc.card.name}" from your collection?`)) return
    await deleteUserTradingCard(uc.id)
    setItems(prev => prev.filter(i => i.id !== uc.id))
    setTotal(t => t - 1)
  }

  const handleSaved = (updated: UserTradingCard) => {
    setItems(prev => prev.map(i => i.id === updated.id ? updated : i))
    setEditing(null)
  }

  const handleSaleSaved = async (ucId: number, transaction_date: string, price?: number | null, notes?: string | null) => {
    const sale = await recordCardSale(ucId, transaction_date, price, notes)
    setItems(prev => prev.map(i => i.id === ucId ? { ...i, sales: [...i.sales, sale] } : i))
    setSelling(null)
  }

  const fmt = (uc: UserTradingCard, key: string): string => {
    if (key === 'available') {
      const avail = availableCardCopies(uc)
      return `${avail}/${uc.count ?? 1}`
    }
    if (key === 'sell_price') {
      const price = latestCardSalePrice(uc)
      return price != null ? `$${price.toFixed(2)}` : '—'
    }
    if (key in uc.card) {
      const v = (uc.card as unknown as Record<string, unknown>)[key]
      if (v === null || v === undefined) return '—'
      if (key === 'average_price') return `$${Number(v).toFixed(2)}`
      return String(v)
    }
    const v = (uc as unknown as Record<string, unknown>)[key]
    if (v === null || v === undefined) return '—'
    if (key === 'paid_price' || key === 'asking_price') return `$${Number(v).toFixed(2)}`
    if (key === 'buy_date') return new Date(v as string).toLocaleDateString()
    if (key === 'for_sale' || key === 'do_not_sell') return v ? '✓' : '—'
    return String(v)
  }

  return (
    <div className="max-w-full px-4 py-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold">My Cards</h1>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setScanning(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition"
          >
            <ScanLine size={15} />
            Scan Card
          </button>
          <button
            onClick={() => setAdding(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
          >
            <Plus size={15} />
            Add Card
          </button>
          <ColumnPicker page="cards" columns={columns} visibility={visibility} onChange={setVisibility} />
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runSearch()}
            placeholder="Search by card name…"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <button onClick={runSearch} className="bg-brand-500 hover:bg-brand-600 text-white font-medium px-5 py-2.5 rounded-lg transition">Search</button>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-16">Loading…</div>
      ) : error ? (
        <div className="text-center py-16">
          <p className="text-lg text-red-400">{error}</p>
          <button
            onClick={fetchCollection}
            className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
          >
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center text-gray-400 py-16">
          <p className="text-lg">No cards found.</p>
          <p className="text-sm mt-1">Click "Add Card" to get started.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
              <tr>
                {visibleCols.map(c => <th key={c.key} className="px-4 py-3 text-left whitespace-nowrap">{c.label}</th>)}
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {items.map(uc => {
                const avail = availableCardCopies(uc)
                return (
                  <tr key={uc.id} className="hover:bg-gray-800/50 transition">
                    {visibleCols.map(c => (
                      <td key={c.key} className="px-4 py-3 whitespace-nowrap text-gray-300">
                        {c.key === 'available' ? (
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                            {avail}/{uc.count ?? 1}
                          </span>
                        ) : c.key === 'image_small' ? (
                          cardCoverImage(uc) ? (
                            <img
                              src={resolveImageUrl(cardCoverImage(uc)) ?? undefined}
                              alt=""
                              className="w-8 h-11 object-cover rounded border border-gray-700"
                            />
                          ) : '—'
                        ) : fmt(uc, c.key)}
                      </td>
                    ))}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setEditing(uc)} title="Edit" className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition">
                          <Pencil size={14} />
                        </button>
                        {!isCollector && (
                          <button
                            onClick={() => setSelling(uc)}
                            title={uc.do_not_sell ? 'Marked Do Not Sell' : 'Record Sale'}
                            disabled={avail === 0 || uc.do_not_sell}
                            className="p-1.5 text-gray-400 hover:text-green-400 hover:bg-gray-700 rounded-lg transition disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            <DollarSign size={14} />
                          </button>
                        )}
                        <button onClick={() => handleDelete(uc)} title="Delete" className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded-lg transition">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && total > 0 && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-400">
          <span>
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-lg border border-gray-700 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ChevronLeft size={16} />
            </button>
            <span>Page {page} of {pageCount}</span>
            <button
              onClick={() => setPage(p => Math.min(pageCount, p + 1))}
              disabled={page === pageCount}
              className="p-2 rounded-lg border border-gray-700 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {editing && (
        <EditTradingCardModal
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}
      {selling && (
        <RecordCardSaleModal
          item={selling}
          onClose={() => setSelling(null)}
          onSaved={handleSaleSaved}
        />
      )}
      {adding && (
        <AddCardModal
          onClose={() => setAdding(false)}
          onAdded={() => { setAdding(false); fetchCollection() }}
        />
      )}
      {scanning && (
        <CardScanModal
          onClose={() => setScanning(false)}
          onAdded={() => { setScanning(false); fetchCollection() }}
          onManualFallback={() => { setScanning(false); setAdding(true) }}
        />
      )}
    </div>
  )
}
