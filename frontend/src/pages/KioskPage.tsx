import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { fetchSignedComics, fetchTodaysPicks } from '../api/kiosk'
import SignupForm from '../components/Kiosk/SignupForm'
import FeaturedLightbox from '../components/Kiosk/FeaturedLightbox'
import SeriesSearch from '../components/Kiosk/SeriesSearch'
import type { KioskCard } from '../types'

export default function KioskPage() {
  const { logout } = useAuth()

  const [todaysPicks, setTodaysPicks] = useState<KioskCard[]>([])
  const [todaysPicksLoading, setTodaysPicksLoading] = useState(true)
  const [todaysPicksError, setTodaysPicksError] = useState<string | null>(null)

  const [signedComics, setSignedComics] = useState<KioskCard[]>([])
  const [signedLoading, setSignedLoading] = useState(true)
  const [signedError, setSignedError] = useState<string | null>(null)

  useEffect(() => {
    fetchTodaysPicks()
      .then(setTodaysPicks)
      .catch((err) => setTodaysPicksError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setTodaysPicksLoading(false))

    fetchSignedComics()
      .then(setSignedComics)
      .catch((err) => setSignedError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setSignedLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-wide">Welcome</h1>
          <button
            onClick={logout}
            className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm font-medium transition"
          >
            Log Out
          </button>
        </div>

        <SignupForm />

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

        <SeriesSearch />
      </div>
    </div>
  )
}
