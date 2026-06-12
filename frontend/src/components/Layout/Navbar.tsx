import { BookOpen, LogOut, Shield, Upload, Search } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-4 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-brand-500 font-bold text-xl">
          <BookOpen size={24} />
          <span>ComicVault</span>
        </Link>

        {user && (
          <div className="flex items-center gap-1 sm:gap-3">
            <Link
              to="/collection"
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800 transition text-sm"
            >
              <Search size={16} />
              <span className="hidden sm:inline">Collection</span>
            </Link>
            <Link
              to="/upload"
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800 transition text-sm"
            >
              <Upload size={16} />
              <span className="hidden sm:inline">Upload</span>
            </Link>
            {user.is_admin && (
              <Link
                to="/admin"
                className="flex items-center gap-1 px-3 py-2 rounded-lg text-yellow-400 hover:text-yellow-300 hover:bg-gray-800 transition text-sm"
              >
                <Shield size={16} />
                <span className="hidden sm:inline">Admin</span>
              </Link>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition text-sm"
            >
              <LogOut size={16} />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        )}
      </div>
    </nav>
  )
}
