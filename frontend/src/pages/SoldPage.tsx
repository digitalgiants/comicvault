import { useEffect, useState, useCallback } from 'react'
import { Search } from 'lucide-react'
import { getSold, getColumnPrefs } from '../api/collection'
import { type SaleWithComic, type ColumnVisibility, SOLD_COLUMNS } from '../types'
import ColumnPicker from '../components/Collection/ColumnPicker'
import BugReportButton from '../components/BugReportButton'

export default function SoldPage() {
  const [items, setItems] = useState<SaleWithComic[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [publisherFilter, setPublisherFilter] = useState('')
  const [visibility, setVisibility] = useState<ColumnVisibility>({})

  useEffect(() => {
    getColumnPrefs('sold').then(p => setVisibility(p.columns))
  }, [])

  const fetchSold = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (search) params.name = search
      if (publisherFilter) params.publisher = publisherFilter
      setItems(await getSold(params))
    } finally {
      setLoading(false)
    }
  }, [search, publisherFilter])

  useEffect(() => { fetchSold() }, [])

  const visibleCols = SOLD_COLUMNS.filter(c => visibility[c.key] !== false)

  const fmt = (sale: SaleWithComic, key: string): string => {
    if (key === 'sell_date') return new Date(sale.sell_date).toLocaleDateString()
    if (key === 'sell_price') return sale.sell_price != null ? `$${sale.sell_price.toFixed(2)}` : '—'
    if (key === 'notes') return sale.notes ?? '—'
    const v = (sale.comic as Record<string, unknown>)[key]
    if (v === null || v === undefined) return '—'
    if (key === 'average_price') return `$${Number(v).toFixed(2)}`
    return String(v)
  }

  return (
    <div className="max-w-full px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Sold / Traded</h1>
          <p className="text-gray-400 text-sm mt-0.5">{items.length} sale{items.length !== 1 ? 's' : ''}</p>
        </div>
        <ColumnPicker page="sold" columns={SOLD_COLUMNS} visibility={visibility} onChange={setVisibility} />
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && fetchSold()}
            placeholder="Search by title…"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <input value={publisherFilter} onChange={e => setPublisherFilter(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchSold()} placeholder="Publisher" className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40" />
        <button onClick={fetchSold} className="bg-brand-500 hover:bg-brand-600 text-white font-medium px-5 py-2.5 rounded-lg transition">Search</button>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-16">Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-center text-gray-400 py-16">
          <p className="text-lg">No sales recorded yet.</p>
          <p className="text-sm mt-1">Use the $ icon in your collection to record a sale.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
              <tr>
                {visibleCols.map(c => <th key={c.key} className="px-4 py-3 text-left whitespace-nowrap">{c.label}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {items.map(sale => (
                <tr key={sale.id} className="hover:bg-gray-800/50 transition">
                  {visibleCols.map(c => (
                    <td key={c.key} className="px-4 py-3 whitespace-nowrap text-gray-300">
                      {fmt(sale, c.key)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <BugReportButton />
    </div>
  )
}
