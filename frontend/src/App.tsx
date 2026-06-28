import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import Navbar from './components/Layout/Navbar'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'
import CollectionPage from './pages/CollectionPage'
import UploadPage from './pages/UploadPage'
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

function AppRoutes() {
  const { user } = useAuth()
  return (
    <div className="min-h-screen">
      <Navbar />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/kiosk" element={<RequireAuth><KioskPage /></RequireAuth>} />
        <Route path="/" element={<RequireNonKiosk><DashboardPage /></RequireNonKiosk>} />
        <Route path="/collection" element={<RequireNonKiosk><CollectionPage /></RequireNonKiosk>} />
        <Route path="/upload" element={<RequireNonKiosk><UploadPage /></RequireNonKiosk>} />
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
