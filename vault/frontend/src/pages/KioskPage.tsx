import { useEffect, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { fetchKioskSeriesItems, fetchSignedComics, fetchTodaysPicks, searchKioskSeries } from '../api/kiosk'
import { resolveImageUrl } from '../api/client'
import KioskHeader from '../components/Kiosk/KioskHeader'
import SignupModal from '../components/Kiosk/SignupModal'
import FeaturedLightbox from '../components/Kiosk/FeaturedLightbox'
import type { KioskCard, SeriesSearchResult } from '../types'

export default function KioskPage() {
  const [todaysPicks, setTodaysPicks] = useState<KioskCard[]>([])
  const [todaysPicksLoading, setTodaysPicksLoading] = useState(true)
  const [todaysPicksError, setTodaysPicksError] = useState<string | null>(null)

  const [signedComics, setSignedComics] = useState<KioskCard[]>([])
  const [signedLoading, setSignedLoading] = useState(true)
  const [signedError, setSignedError] = useState<string | null>(null)

  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [seriesResults, setSeriesResults] = useState<SeriesSearchResult[]>([])

  const [selectedSeries, setSelectedSeries] = useState<string | null>(null)
  const [seriesItems, setSeriesItems] = useState<KioskCard[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)

  const [signupOpen, setSignupOpen] = useState(false)
  const [showConfirmation, setShowConfirmation] = useState(false)
  const confirmationTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    fetchTodaysPicks()
      .then(setTodaysPicks)
      .catch((err) => setTodaysPicksError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setTodaysPicksLoading(false))

    fetchSignedComics()
      .then(setSignedComics)
      .catch((err) => setSignedError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setSignedLoading(false))

    return () => clearTimeout(confirmationTimer.current)
  }, [])

  const runSearch = () => {
    const trimmed = query.trim()
    if (trimmed.length < 2) return

    setSearching(true)
    setHasSearched(true)
    setSelectedSeries(null)
    setSeriesItems([])
    searchKioskSeries(trimmed)
      .then(setSeriesResults)
      .catch(() => setSeriesResults([]))
      .finally(() => setSearching(false))
  }

  const clearSearch = () => {
    setQuery('')
    setHasSearched(false)
    setSeriesResults([])
    setSelectedSeries(null)
    setSeriesItems([])
  }

  const selectSeries = (name: string) => {
    setSelectedSeries(name)
    setItemsLoading(true)
    fetchKioskSeriesItems(name)
      .then(setSeriesItems)
      .finally(() => setItemsLoading(false))
  }

  const handleSignupSuccess = () => {
    setSignupOpen(false)
    setShowConfirmation(true)
    clearTimeout(confirmationTimer.current)
    confirmationTimer.current = setTimeout(() => setShowConfirmation(false), 6000)
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <KioskHeader
        query={query}
        onQueryChange={setQuery}
        onSearch={runSearch}
        searching={searching}
        onOpenSignup={() => setSignupOpen(true)}
        showConfirmation={showConfirmation}
      />

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {hasSearched ? (
          <div>
            <div className="flex items-center gap-3 mb-4">
              {selectedSeries && (
                <>
                  <button
                    onClick={() => setSelectedSeries(null)}
                    className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition"
                  >
                    <ArrowLeft size={16} />
                    Back to series results
                  </button>
                  <span className="text-gray-700">|</span>
                </>
              )}
              <button
                onClick={clearSearch}
                className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition"
              >
                <ArrowLeft size={16} />
                Back to Today's Picks
              </button>
            </div>

            {selectedSeries ? (
              <>
                <h2 className="font-semibold text-lg mb-4">{selectedSeries}</h2>
                {itemsLoading ? (
                  <p className="text-gray-400">Loading…</p>
                ) : seriesItems.length === 0 ? (
                  <p className="text-gray-500 italic">No issues found for this series.</p>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                    {seriesItems.map((item) => (
                      <div key={item.id} className="bg-gray-800 rounded-lg overflow-hidden">
                        {item.img ? (
                          <img
                            src={resolveImageUrl(item.img) ?? undefined}
                            alt={`#${item.issue_number ?? '?'}`}
                            className="w-full aspect-[2/3] object-cover"
                          />
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
              </>
            ) : searching ? (
              <p className="text-gray-400">Searching…</p>
            ) : seriesResults.length === 0 ? (
              <p className="text-gray-500 italic">No matching series found — try a different title.</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                {seriesResults.map((r) => (
                  <button
                    key={r.name}
                    onClick={() => selectSeries(r.name)}
                    className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 text-left transition"
                  >
                    <p className="font-medium truncate">{r.name}</p>
                    <p className="text-xs text-gray-500 mt-1">{r.count} issue{r.count === 1 ? '' : 's'}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <FeaturedLightbox
              title="Today's Picks"
              items={todaysPicks}
              loading={todaysPicksLoading}
              error={todaysPicksError}
            />

            <FeaturedLightbox
              title="Signed Comics"
              items={signedComics}
              loading={signedLoading}
              error={signedError}
            />
          </>
        )}
      </div>

      {signupOpen && (
        <SignupModal onClose={() => setSignupOpen(false)} onSuccess={handleSignupSuccess} />
      )}
    </div>
  )
}
