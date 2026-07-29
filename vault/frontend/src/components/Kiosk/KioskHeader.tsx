import { BookOpen, CheckCircle2, LogOut, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

interface Props {
  query: string
  onQueryChange: (value: string) => void
  onSearch: () => void
  searching: boolean
  onOpenSignup: () => void
  showConfirmation: boolean
}

export default function KioskHeader({ query, onQueryChange, onSearch, searching, onOpenSignup, showConfirmation }: Props) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-20 bg-gray-900 border-b border-gray-800 shadow-lg shadow-black/20">
      <div className="max-w-5xl mx-auto px-4 py-4 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2 text-brand-500 font-bold text-xl">
            <BookOpen size={26} />
            <span>ComicVault</span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-gray-800 border border-gray-700 hover:bg-gray-700 text-gray-300 hover:text-white text-sm font-medium transition flex-shrink-0"
          >
            <LogOut size={16} />
            Log Out
          </button>
        </div>

        <p className="text-gray-300 text-sm leading-relaxed">
          Welcome! Browse our collection below, search for a favorite series, or sign up and we'll let you know when new issues come in.
        </p>

        <div className="flex flex-wrap gap-2.5">
          <div className="relative flex-1 min-w-[220px] flex gap-2">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && onSearch()}
                placeholder="Search for a series…"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <button
              onClick={onSearch}
              disabled={searching || query.trim().length < 2}
              className="px-5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition"
            >
              {searching ? 'Searching…' : 'Search'}
            </button>
          </div>
          <button
            onClick={onOpenSignup}
            className="px-5 py-2.5 rounded-lg border border-brand-600 text-brand-400 hover:bg-brand-500 hover:text-white text-sm font-semibold transition"
          >
            Sign Up
          </button>
        </div>

        {showConfirmation && (
          <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 text-green-400 text-sm font-medium rounded-lg px-3.5 py-2.5">
            <CheckCircle2 size={16} className="flex-shrink-0" />
            Thank you! Please feel free to peruse our collection.
          </div>
        )}
      </div>
    </header>
  )
}
