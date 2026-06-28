import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { getCollection } from '../api/collection'
import { availableCopies, type UserComic } from '../types'

export default function KioskPage() {
  const { user, logout } = useAuth()
  const [items, setItems] = useState<UserComic[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getCollection(search ? { name: search } : undefined)
      .then(setItems)
      .finally(() => setLoading(false))
  }, [search])

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold tracking-wide">Available Comics</h1>
          <button
            onClick={logout}
            className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm font-medium transition"
          >
            Log Out
          </button>
        </div>

        <input
          type="text"
          placeholder="Search by title…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full mb-6 px-4 py-2 rounded bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        {loading ? (
          <div className="text-center text-gray-500 py-20">Loading…</div>
        ) : items.length === 0 ? (
          <div className="text-center text-gray-500 py-20">No available comics found.</div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {items.map(uc => {
              const avail = availableCopies(uc)
              return (
                <div key={uc.id} className="bg-gray-800 rounded-lg overflow-hidden flex flex-col">
                  {uc.comic.cover_image_url ? (
                    <img
                      src={uc.comic.cover_image_url}
                      alt={uc.comic.name}
                      className="w-full aspect-[2/3] object-cover"
                    />
                  ) : (
                    <div className="w-full aspect-[2/3] bg-gray-700 flex items-center justify-center text-gray-500 text-xs text-center px-2">
                      No Cover
                    </div>
                  )}
                  <div className="p-3 flex flex-col gap-1 flex-1">
                    <p className="text-sm font-semibold leading-tight line-clamp-2">{uc.comic.name}</p>
                    {uc.comic.number && (
                      <p className="text-xs text-gray-400">#{uc.comic.number}{uc.comic.volume ? ` Vol.${uc.comic.volume}` : ''}</p>
                    )}
                    {uc.comic.publisher && (
                      <p className="text-xs text-gray-500">{uc.comic.publisher}</p>
                    )}
                    {uc.comic.writer && (
                      <p className="text-xs text-gray-500 italic">{uc.comic.writer}</p>
                    )}
                    <div className="mt-auto pt-2 flex items-center justify-between">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                        {avail} available
                      </span>
                      {uc.comic.average_price != null && (
                        <span className="text-xs text-gray-400">${uc.comic.average_price.toFixed(2)}</span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
