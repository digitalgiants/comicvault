import { useEffect, useState, useCallback } from 'react'
import { Search, Pencil, DollarSign, Trash2 } from 'lucide-react'
import { getCollection, recordSale, deleteUserComic, getColumnPrefs } from '../api/collection'
import { availableCopies, type UserComic, type ColumnVisibility, COLLECTION_COLUMNS } from '../types'
import EditComicModal from '../components/Collection/EditComicModal'
import BulkEditModal from '../components/Collection/BulkEditModal'
import ColumnPicker from '../components/Collection/ColumnPicker'
import BugReportButton from '../components/BugReportButton'
import RecordSaleModal from '../components/Collection/RecordSaleModal'

export default function CollectionPage() {
  const [items, setItems] = useState<UserComic[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [publisherFilter, setPublisherFilter] = useState('')
  const [writerFilter, setWriterFilter] = useState('')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [editing, setEditing] = useState<UserComic | null>(null)
  const [selling, setSelling] = useState<UserComic | null>(null)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [visibility, setVisibility] = useState<ColumnVisibility>({})
  const [activeComic, setActiveComic] = useState<UserComic | null>(null)

  useEffect(() => {
    getColumnPrefs('collection').then(p => setVisibility(p.columns))
  }, [])

  const fetchCollection = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (search) params.name = search
      if (publisherFilter) params.publisher = publisherFilter
      if (writerFilter) params.writer = writerFilter
      setItems(await getCollection(params))
    } finally {
      setLoading(false)
    }
  }, [search, publisherFilter, writerFilter])

  useEffect(() => { fetchCollection() }, [])

  const visibleCols = COLLECTION_COLUMNS.filter(c => visibility[c.key] !== false)

  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelected(prev => prev.size === items.length ? new Set() : new Set(items.map(i => i.id)))
  }

  const handleDelete = async (uc: UserComic) => {
    if (!confirm(`Permanently delete "${uc.comic.name}" from your collection?`)) return
    await deleteUserComic(uc.id)
    setItems(prev => prev.filter(i => i.id !== uc.id))
    setSelected(prev => { const n = new Set(prev); n.delete(uc.id); return n })
  }

  const handleSaved = (updated: UserComic) => {
    setItems(prev => prev.map(i => i.id === updated.id ? updated : i))
    setEditing(null)
  }

  const handleSaleSaved = async (ucId: number, sell_date: string, sell_price?: number | null, notes?: string | null) => {
    const sale = await recordSale(ucId, sell_date, sell_price, notes)
    setItems(prev => prev.map(i => i.id === ucId ? { ...i, sales: [...i.sales, sale] } : i))
    setSelling(null)
  }

  const selectedItems = items.filter(i => selected.has(i.id))

  const fmt = (uc: UserComic, key: string): string => {
    if (key === 'available') {
      const avail = availableCopies(uc)
      return `${avail}/${uc.number_of_books ?? 1}`
    }
    if (key in uc.comic) {
      const v = (uc.comic as Record<string, unknown>)[key]
      if (v === null || v === undefined) return '—'
      if (key === 'average_price') return `$${Number(v).toFixed(2)}`
      if (key === 'direct') return v ? 'Yes' : 'No'
      return String(v)
    }
    const v = (uc as Record<string, unknown>)[key]
    if (v === null || v === undefined) return '—'
    if (key === 'price_paid') return `$${Number(v).toFixed(2)}`
    if (key === 'signed' || key === 'remarked') return v ? '✓' : '—'
    if (key === 'buy_date') return new Date(v as string).toLocaleDateString()
    return String(v)
  }

  return (
    <div className="max-w-full px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">My Collection</h1>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button
              onClick={() => setBulkOpen(true)}
              className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
            >
              Bulk Edit ({selected.size})
            </button>
          )}
          <ColumnPicker page="collection" columns={COLLECTION_COLUMNS} visibility={visibility} onChange={setVisibility} />
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && fetchCollection()}
            placeholder="Search by title…"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <input value={publisherFilter} onChange={e => setPublisherFilter(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchCollection()} placeholder="Publisher" className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40" />
        <input value={writerFilter} onChange={e => setWriterFilter(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchCollection()} placeholder="Writer" className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40" />
        <button onClick={fetchCollection} className="bg-brand-500 hover:bg-brand-600 text-white font-medium px-5 py-2.5 rounded-lg transition">Search</button>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-16">Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-center text-gray-400 py-16">
          <p className="text-lg">No comics found.</p>
          <p className="text-sm mt-1">Upload a CSV to get started.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
              <tr>
                <th className="px-3 py-3">
                  <input type="checkbox" checked={selected.size === items.length && items.length > 0} onChange={toggleAll} className="w-3.5 h-3.5 rounded accent-brand-500" />
                </th>
                {visibleCols.map(c => <th key={c.key} className="px-4 py-3 text-left whitespace-nowrap">{c.label}</th>)}
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {items.map(uc => {
                const avail = availableCopies(uc)
                return (
                  <tr key={uc.id} className={`hover:bg-gray-800/50 transition ${selected.has(uc.id) ? 'bg-gray-800/30' : ''}`}>
                    <td className="px-3 py-3">
                      <input type="checkbox" checked={selected.has(uc.id)} onChange={() => toggleSelect(uc.id)} className="w-3.5 h-3.5 rounded accent-brand-500" />
                    </td>
                    {visibleCols.map(c => (
                      <td key={c.key} className="px-4 py-3 whitespace-nowrap text-gray-300">
                        {c.key === 'available' ? (
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                            {avail}/{uc.number_of_books ?? 1}
                          </span>
                        ) : fmt(uc, c.key)}
                      </td>
                    ))}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => { setEditing(uc); setActiveComic(uc) }} title="Edit" className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition">
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => setSelling(uc)}
                          title="Record Sale"
                          disabled={avail === 0}
                          className="p-1.5 text-gray-400 hover:text-green-400 hover:bg-gray-700 rounded-lg transition disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <DollarSign size={14} />
                        </button>
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

      {editing && (
        <EditComicModal
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
          onItemChange={updated => setItems(prev => prev.map(i => i.id === updated.id ? updated : i))}
        />
      )}
      {selling && (
        <RecordSaleModal
          item={selling}
          onClose={() => setSelling(null)}
          onSaved={handleSaleSaved}
        />
      )}
      {bulkOpen && <BulkEditModal selected={selectedItems} onClose={() => setBulkOpen(false)} onSaved={() => { setBulkOpen(false); setSelected(new Set()); fetchCollection() }} />}
      <BugReportButton activeComic={activeComic} />
    </div>
  )
}
