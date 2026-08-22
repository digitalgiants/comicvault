import { useEffect } from 'react'
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import Navbar from './components/Layout/Navbar'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'
import CollectionPage from './pages/CollectionPage'
import CardsPage from './pages/CardsPage'
import UploadPage from './pages/UploadPage'
import ScanPage from './pages/ScanPage'
import SearchPage from './pages/SearchPage'
import AdminPage from './pages/AdminPage'
import SoldPage from './pages/SoldPage'
import KioskPage from './pages/KioskPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user?.is_admin ? <>{children}</> : <Navigate to="/" replace />
}

function RequireNonKiosk({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  return user.is_kiosk ? <Navigate to="/kiosk" replace /> : <>{children}</>
}

const DEFAULT_VIEWPORT = 'width=device-width, initial-scale=1.0'
const KIOSK_VIEWPORT = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no'

function AppRoutes() {
  const { user } = useAuth()

  useEffect(() => {
    const meta = document.querySelector('meta[name="viewport"]')
    if (!meta) return
    meta.setAttribute('content', user?.is_kiosk ? KIOSK_VIEWPORT : DEFAULT_VIEWPORT)
    return () => meta.setAttribute('content', DEFAULT_VIEWPORT)
  }, [user?.is_kiosk])

  return (
    <div className={`min-h-screen ${user?.is_kiosk ? 'touch-manipulation' : ''}`}>
      {!user?.is_kiosk && <Navbar />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/kiosk" element={<RequireAuth><KioskPage /></RequireAuth>} />
        <Route path="/" element={<RequireNonKiosk><DashboardPage /></RequireNonKiosk>} />
        <Route path="/comics" element={<RequireNonKiosk><CollectionPage /></RequireNonKiosk>} />
        <Route path="/collection" element={<Navigate to="/comics" replace />} />
        <Route path="/cards" element={<RequireNonKiosk><CardsPage /></RequireNonKiosk>} />
        <Route path="/upload" element={<RequireNonKiosk><UploadPage /></RequireNonKiosk>} />
        <Route path="/scan" element={<RequireNonKiosk><ScanPage /></RequireNonKiosk>} />
        <Route path="/search" element={<RequireNonKiosk><SearchPage /></RequireNonKiosk>} />
        <Route path="/sold" element={<RequireNonKiosk><SoldPage /></RequireNonKiosk>} />
        <Route path="/admin" element={<RequireAdmin><AdminPage /></RequireAdmin>} />
        <Route path="*" element={user?.is_kiosk ? <Navigate to="/kiosk" replace /> : <Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  )
}
