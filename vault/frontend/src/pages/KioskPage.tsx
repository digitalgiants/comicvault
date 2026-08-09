import { useEffect, useRef, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import {
  fetchKioskSeriesItems, fetchSignedComics, fetchTodaysPicks, searchKioskSeries,
  fetchCardsTodaysPicks, fetchGradedCards, searchKioskCards, fetchKioskCardItems,
} from '../api/kiosk'
import { resolveImageUrl } from '../api/client'
import KioskHeader from '../components/Kiosk/KioskHeader'
import SignupModal from '../components/Kiosk/SignupModal'
import FeaturedLightbox from '../components/Kiosk/FeaturedLightbox'
import FeaturedCardLightbox from '../components/Kiosk/FeaturedCardLightbox'
import type { KioskCard, KioskTradingCard, SeriesSearchResult } from '../types'

type Mode = 'comics' | 'cards'

export default function KioskPage() {
  const [mode, setMode] = useState<Mode>('comics')

  const [todaysPicks, setTodaysPicks] = useState<KioskCard[]>([])
  const [todaysPicksLoading, setTodaysPicksLoading] = useState(true)
  const [todaysPicksError, setTodaysPicksError] = useState<string | null>(null)

  const [signedComics, setSignedComics] = useState<KioskCard[]>([])
  const [signedLoading, setSignedLoading] = useState(true)
  const [signedError, setSignedError] = useState<string | null>(null)

  const [cardsTodaysPicks, setCardsTodaysPicks] = useState<KioskTradingCard[]>([])
  const [cardsTodaysPicksLoading, setCardsTodaysPicksLoading] = useState(true)
  const [cardsTodaysPicksError, setCardsTodaysPicksError] = useState<string | null>(null)

  const [gradedCards, setGradedCards] = useState<KioskTradingCard[]>([])
  const [gradedLoading, setGradedLoading] = useState(true)
  const [gradedError, setGradedError] = useState<string | null>(null)

  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  // Comics search results
  const [seriesResults, setSeriesResults] = useState<SeriesSearchResult[]>([])
  const [selectedSeries, setSelectedSeries] = useState<string | null>(null)
  const [seriesItems, setSeriesItems] = useState<KioskCard[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)

  // Card search results
  const [cardResults, setCardResults] = useState<SeriesSearchResult[]>([])
  const [selectedCardName, setSelectedCardName] = useState<string | null>(null)
  const [cardItems, setCardItems] = useState<KioskTradingCard[]>([])
  const [cardItemsLoading, setCardItemsLoading] = useState(false)

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

    fetchCardsTodaysPicks()
      .then(setCardsTodaysPicks)
      .catch((err) => setCardsTodaysPicksError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setCardsTodaysPicksLoading(false))

    fetchGradedCards()
      .then(setGradedCards)
      .catch((err) => setGradedError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setGradedLoading(false))

    return () => clearTimeout(confirmationTimer.current)
  }, [])

  const runSearch = () => {
    const trimmed = query.trim()
    if (trimmed.length < 2) return

    setSearching(true)
    setHasSearched(true)
    setSelectedSeries(null)
    setSeriesItems([])
    setSelectedCardName(null)
    setCardItems([])

    if (mode === 'comics') {
      searchKioskSeries(trimmed)
        .then(setSeriesResults)
        .catch(() => setSeriesResults([]))
        .finally(() => setSearching(false))
    } else {
      searchKioskCards(trimmed)
        .then(setCardResults)
        .catch(() => setCardResults([]))
        .finally(() => setSearching(false))
    }
  }

  const clearSearch = () => {
    setQuery('')
    setHasSearched(false)
    setSeriesResults([])
    setSelectedSeries(null)
    setSeriesItems([])
    setCardResults([])
    setSelectedCardName(null)
    setCardItems([])
  }

  const switchMode = (next: Mode) => {
    setMode(next)
    clearSearch()
  }

  const selectSeries = (name: string) => {
    setSelectedSeries(name)
    setItemsLoading(true)
    fetchKioskSeriesItems(name)
      .then(setSeriesItems)
      .finally(() => setItemsLoading(false))
  }

  const selectCardName = (name: string) => {
    setSelectedCardName(name)
    setCardItemsLoading(true)
    fetchKioskCardItems(name)
      .then(setCardItems)
      .finally(() => setCardItemsLoading(false))
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
        searchPlaceholder={mode === 'comics' ? 'Search for a series…' : 'Search for a card…'}
      />

      <div className="max-w-5xl mx-auto px-4 pt-4">
        <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1 w-fit">
          {(['comics', 'cards'] as const).map((m) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition ${mode === m ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}
            >
              {m === 'comics' ? 'Comics' : 'Cards'}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {hasSearched ? (
          mode === 'comics' ? (
            <div>
              <div className="flex flex-wrap items-center gap-3 mb-4">
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
            <div>
              <div className="flex flex-wrap items-center gap-3 mb-4">
                {selectedCardName && (
                  <>
                    <button
                      onClick={() => setSelectedCardName(null)}
                      className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition"
                    >
                      <ArrowLeft size={16} />
                      Back to card results
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

              {selectedCardName ? (
                <>
                  <h2 className="font-semibold text-lg mb-4">{selectedCardName}</h2>
                  {cardItemsLoading ? (
                    <p className="text-gray-400">Loading…</p>
                  ) : cardItems.length === 0 ? (
                    <p className="text-gray-500 italic">No copies found for this card.</p>
                  ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                      {cardItems.map((item) => (
                        <div key={item.id} className="bg-gray-800 rounded-lg overflow-hidden">
                          {item.img ? (
                            <img
                              src={resolveImageUrl(item.img) ?? undefined}
                              alt={`${item.name} #${item.card_number ?? '?'}`}
                              className="w-full aspect-[2/3] object-cover"
                            />
                          ) : (
                            <div className="w-full aspect-[2/3] bg-gray-700 flex items-center justify-center text-gray-500 text-xs text-center px-1">
                              {item.set_name ?? item.name}
                            </div>
                          )}
                          <div className="px-2 py-1.5 text-center">
                            <p className="text-xs text-gray-300">{item.set_name ?? '—'}</p>
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
              ) : cardResults.length === 0 ? (
                <p className="text-gray-500 italic">No matching cards found — try a different name.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  {cardResults.map((r) => (
                    <button
                      key={r.name}
                      onClick={() => selectCardName(r.name)}
                      className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 text-left transition"
                    >
                      <p className="font-medium truncate">{r.name}</p>
                      <p className="text-xs text-gray-500 mt-1">{r.count} cop{r.count === 1 ? 'y' : 'ies'}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        ) : mode === 'comics' ? (
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
        ) : (
          <>
            <FeaturedCardLightbox
              title="Today's Picks"
              items={cardsTodaysPicks}
              loading={cardsTodaysPicksLoading}
              error={cardsTodaysPicksError}
            />

            <FeaturedCardLightbox
              title="Graded Cards"
              items={gradedCards}
              loading={gradedLoading}
              error={gradedError}
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
