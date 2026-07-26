import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchKioskSeriesItems, searchKioskSeries } from '../../api/kiosk'
import type { KioskCard, SeriesSearchResult } from '../../types'

export default function SeriesSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SeriesSearchResult[]>([])
  const [selectedSeries, setSelectedSeries] = useState<string | null>(null)
  const [items, setItems] = useState<KioskCard[]>([])
  const [loadingItems, setLoadingItems] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (selectedSeries !== null || query.trim().length < 2) {
      setResults([])
      return
    }

    let cancelled = false
    const timeout = setTimeout(() => {
      searchKioskSeries(query)
        .then((r) => {
          if (!cancelled) setResults(r)
        })
        .catch(() => {
          if (!cancelled) setResults([])
        })
    }, 200)

    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [query, selectedSeries])

  async function selectSeries(name: string) {
    setSelectedSeries(name)
    setResults([])
    setQuery(name)
    setLoadingItems(true)
    setError(null)
    try {
      setItems(await fetchKioskSeriesItems(name))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load series')
    } finally {
      setLoadingItems(false)
    }
  }

  return (
    <section className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
      <h2 className="font-semibold text-lg mb-4">Search Series</h2>
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSelectedSeries(null)
            setItems([])
          }}
          placeholder="Search for a series…"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        {results.length > 0 && (
          <ul className="absolute z-10 mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
            {results.map((r) => (
              <li key={r.name}>
                <button
                  type="button"
                  onClick={() => void selectSeries(r.name)}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gray-700 transition"
                >
                  {r.name} <span className="text-gray-500">({r.count})</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {loadingItems && <p className="text-gray-400 text-sm mt-4">Loading…</p>}
      {error && <p className="text-red-400 text-sm mt-4">{error}</p>}

      {selectedSeries && !loadingItems && !error && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 mt-4">
          {items.map((item) => (
            <div key={item.id} className="bg-gray-800 rounded-lg overflow-hidden">
              {item.img ? (
                <img src={item.img} alt={`#${item.issue_number ?? '?'}`} className="w-full aspect-[2/3] object-cover" />
              ) : (
                <div className="w-full aspect-[2/3] bg-gray-700 flex items-center justify-center text-gray-500 text-xs">
                  #{item.issue_number}
                </div>
              )}
              <div className="px-2 py-1.5 text-center">
                <p className="text-xs text-gray-300">#{item.issue_number}</p>
                {item.average_price != null && (
                  <p className="text-xs text-green-400">${item.average_price.toFixed(2)}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
