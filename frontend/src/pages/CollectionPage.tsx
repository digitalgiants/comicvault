import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import api from '../api/client'

interface Comic {
  id: number
  publisher: string | null
  name: string
  volume: string | null
  number: string | null
  variant: string | null
  writer: string | null
  artist: string | null
}

interface UserComic {
  id: number
  comic: Comic
  number_of_books: number
  price_paid: number | null
  signed: boolean
  remarked: boolean
  notes: string | null
  buy_date: string | null
  sell_date: string | null
}

export default function CollectionPage() {
  const [items, setItems] = useState<UserComic[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [publisherFilter, setPublisherFilter] = useState('')
  const [writerFilter, setWriterFilter] = useState('')

  const fetchCollection = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (search) params.name = search
      if (publisherFilter) params.publisher = publisherFilter
      if (writerFilter) params.writer = writerFilter
      const { data } = await api.get('/comics/collection', { params })
      setItems(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchCollection() }, [])

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">My Collection</h1>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchCollection()}
            placeholder="Search by title…"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <input
          value={publisherFilter}
          onChange={(e) => setPublisherFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetchCollection()}
          placeholder="Publisher"
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40"
        />
        <input
          value={writerFilter}
          onChange={(e) => setWriterFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetchCollection()}
          placeholder="Writer"
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40"
        />
        <button
          onClick={fetchCollection}
          className="bg-brand-500 hover:bg-brand-600 text-white font-medium px-5 py-2.5 rounded-lg transition"
        >
          Search
        </button>
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
                <th className="px-4 py-3 text-left">Publisher</th>
                <th className="px-4 py-3 text-left">Title</th>
                <th className="px-4 py-3 text-left">Vol</th>
                <th className="px-4 py-3 text-left">#</th>
                <th className="px-4 py-3 text-left">Variant</th>
                <th className="px-4 py-3 text-left">Writer</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Paid</th>
                <th className="px-4 py-3 text-center">Signed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {items.map((uc) => (
                <tr key={uc.id} className="hover:bg-gray-800/50 transition">
                  <td className="px-4 py-3 text-gray-400">{uc.comic.publisher ?? '—'}</td>
                  <td className="px-4 py-3 font-medium">{uc.comic.name}</td>
                  <td className="px-4 py-3 text-gray-400">{uc.comic.volume ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-400">{uc.comic.number ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-400">{uc.comic.variant ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-400">{uc.comic.writer ?? '—'}</td>
                  <td className="px-4 py-3 text-right">{uc.number_of_books}</td>
                  <td className="px-4 py-3 text-right">
                    {uc.price_paid != null ? `$${uc.price_paid.toFixed(2)}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {uc.signed ? (
                      <span className="text-green-400 font-bold">✓</span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
