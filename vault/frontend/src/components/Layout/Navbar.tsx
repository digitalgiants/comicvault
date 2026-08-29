import { BookOpen, LogOut, Shield, Upload, Search, ScanBarcode, Library, Tag, CreditCard, Menu, X, Bug } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import BugReportModal from './BugReportModal'

const NAV_LINKS = [
  { to: '/comics', label: 'Comics', icon: Search },
  { to: '/cards', label: 'Cards', icon: CreditCard },
  { to: '/upload', label: 'Upload', icon: Upload },
  { to: '/scan', label: 'Scan', icon: ScanBarcode },
  { to: '/search', label: 'Search', icon: Library },
  { to: '/sold', label: 'Sold', icon: Tag },
]

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [bugReportOpen, setBugReportOpen] = useState(false)

  const handleLogout = () => {
    setMenuOpen(false)
    logout()
    navigate('/login')
  }

  const navLinks = NAV_LINKS.filter(({ to }) => to !== '/sold' || !user?.is_collector)

  return (
    <nav className="sticky top-0 z-30 bg-gray-900 border-b border-gray-800 px-4 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <Link
          to={user?.is_kiosk ? '/kiosk' : '/'}
          onClick={() => setMenuOpen(false)}
          className="flex items-center gap-2 text-brand-500 font-bold text-xl"
        >
          <BookOpen size={24} />
          <span>ComicVault</span>
        </Link>

        {user && (
          <>
            {/* Desktop / tablet nav */}
            <div className="hidden md:flex items-center gap-1 lg:gap-3">
              {!user.is_kiosk && (
                <>
                  {navLinks.map(({ to, label, icon: Icon }) => (
                    <Link
                      key={to}
                      to={to}
                      className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800 transition text-sm"
                    >
                      <Icon size={16} />
                      <span className="hidden lg:inline">{label}</span>
                    </Link>
                  ))}
                  {user.is_admin && (
                    <Link
                      to="/admin"
                      className="flex items-center gap-1 px-3 py-2 rounded-lg text-yellow-400 hover:text-yellow-300 hover:bg-gray-800 transition text-sm"
                    >
                      <Shield size={16} />
                      <span className="hidden lg:inline">Admin</span>
                    </Link>
                  )}
                </>
              )}
              <button
                onClick={() => setBugReportOpen(true)}
                className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition text-sm"
              >
                <Bug size={16} />
                <span className="hidden lg:inline">Report a Bug</span>
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 px-3 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition text-sm"
              >
                <LogOut size={16} />
                <span className="hidden lg:inline">Logout</span>
              </button>
            </div>

            {/* Mobile / small-tablet menu toggle */}
            <button
              onClick={() => setMenuOpen((open) => !open)}
              className="md:hidden flex items-center justify-center w-10 h-10 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800 transition"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            >
              {menuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </>
        )}
      </div>

      {user && menuOpen && (
        <div className="md:hidden max-w-7xl mx-auto mt-3 pt-3 border-t border-gray-800 flex flex-col gap-1">
          {!user.is_kiosk && (
            <>
              {navLinks.map(({ to, label, icon: Icon }) => (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-gray-300 hover:text-white hover:bg-gray-800 transition text-sm"
                >
                  <Icon size={18} />
                  {label}
                </Link>
              ))}
              {user.is_admin && (
                <Link
                  to="/admin"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-yellow-400 hover:text-yellow-300 hover:bg-gray-800 transition text-sm"
                >
                  <Shield size={18} />
                  Admin
                </Link>
              )}
            </>
          )}
          <button
            onClick={() => { setMenuOpen(false); setBugReportOpen(true) }}
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition text-sm"
          >
            <Bug size={18} />
            Report a Bug
          </button>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition text-sm"
          >
            <LogOut size={18} />
            Logout
          </button>
        </div>
      )}

      <BugReportModal open={bugReportOpen} onClose={() => setBugReportOpen(false)} />
    </nav>
  )
}
