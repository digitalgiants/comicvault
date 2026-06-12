import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload, BookOpen, Search } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'

export default function DashboardPage() {
  const { user } = useAuth()
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    api.get('/comics/collection', { params: { limit: 1 } })
      .then(({ data }) => setCount(data.length))
      .catch(() => {})
  }, [])

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-2">Welcome back</h1>
        <p className="text-gray-400">{user?.email}</p>
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
    </div>
  )
}
