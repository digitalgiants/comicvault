import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload, BookOpen, Search, X } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'
import CollectionGraph from '../components/Dashboard/CollectionGraph'
import BugReportButton from '../components/BugReportButton'

export default function DashboardPage() {
  const { user } = useAuth()
  const [count, setCount] = useState<number | null>(null)
  // Reappears each session on purpose (no localStorage) - it's a low-effort
  // prompt for Collector accounts, not a one-time announcement.
  const [showSellerBanner, setShowSellerBanner] = useState(true)

  useEffect(() => {
    api.get('/comics/collection', { params: { limit: 1 } })
      .then(({ data }) => setCount(data.length))
      .catch(() => {})
  }, [])

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {user?.is_collector && showSellerBanner && (
        <div className="mb-8 bg-brand-500/10 border border-brand-500/30 rounded-xl px-4 py-3 flex items-start gap-3">
          <p className="text-sm text-gray-200 flex-1">
            <span className="font-semibold">Want to sell through ComicVault?</span>{' '}
            Your account is currently set up for tracking your collection. To unlock pricing, listings, and
            sales tools, email{' '}
            <a href="mailto:andrew@comicvaults.com" className="text-brand-400 hover:text-brand-300 underline">
              andrew@comicvaults.com
            </a>{' '}
            and we'll get you set up.
          </p>
          <button
            onClick={() => setShowSellerBanner(false)}
            title="Dismiss"
            className="flex-shrink-0 text-gray-500 hover:text-gray-300 transition"
          >
            <X size={16} />
          </button>
        </div>
      )}

      <div className="mb-10">
        <CollectionGraph />
      </div>

      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-2">Welcome back</h1>
        <p className="text-gray-400">{user?.username}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link
          to="/upload"
          className="bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-2xl p-6 flex flex-col items-center gap-3 transition group"
        >
          <div className="bg-brand-500/20 rounded-xl p-3 group-hover:bg-brand-500/30 transition">
            <Upload size={28} className="text-brand-500" />
          </div>
          <span className="font-semibold">Upload CSV</span>
          <span className="text-gray-400 text-sm text-center">Import your collection from a spreadsheet</span>
        </Link>

        <Link
          to="/collection"
          className="bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-2xl p-6 flex flex-col items-center gap-3 transition group"
        >
          <div className="bg-blue-500/20 rounded-xl p-3 group-hover:bg-blue-500/30 transition">
            <BookOpen size={28} className="text-blue-400" />
          </div>
          <span className="font-semibold">My Collection</span>
          <span className="text-gray-400 text-sm text-center">
            {count !== null ? `${count}+ comics in your vault` : 'Browse your comics'}
          </span>
        </Link>

        <Link
          to="/collection"
          className="bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-2xl p-6 flex flex-col items-center gap-3 transition group"
        >
          <div className="bg-green-500/20 rounded-xl p-3 group-hover:bg-green-500/30 transition">
            <Search size={28} className="text-green-400" />
          </div>
          <span className="font-semibold">Search</span>
          <span className="text-gray-400 text-sm text-center">Filter by title, writer, publisher & more</span>
        </Link>
      </div>
      <BugReportButton />
    </div>
  )
}
