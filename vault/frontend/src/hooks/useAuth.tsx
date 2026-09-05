import React, { createContext, useContext, useEffect, useState } from 'react'
import api from '../api/client'

interface User {
  id: number
  username: string
  email: string | null
  is_admin: boolean
  is_kiosk: boolean
  is_collector: boolean
  is_suspended: boolean
  is_idle_exempt: boolean
  has_seen_tour: boolean
  created_at: string
}

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  signup: (username: string, password: string, isCollector: boolean) => Promise<void>
  loginWithGoogle: (credential: string) => Promise<void>
  markTourSeen: () => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { setLoading(false); return }
    api.get('/auth/me')
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string) => {
    const { data } = await api.post('/auth/login', { username, password })
    localStorage.setItem('token', data.access_token)
    const me = await api.get('/auth/me')
    setUser(me.data)
  }

  const signup = async (username: string, password: string, isCollector: boolean) => {
    await api.post('/auth/signup', { username, password, is_collector: isCollector })
    await login(username, password)
  }

  const loginWithGoogle = async (credential: string) => {
    const { data } = await api.post('/auth/google-login', { credential })
    localStorage.setItem('token', data.access_token)
    const me = await api.get('/auth/me')
    setUser(me.data)
  }

  const markTourSeen = async () => {
    const { data } = await api.post('/auth/tour-seen')
    setUser(data)
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  useEffect(() => {
    if (!user) return

    const idleTimeoutMs = user.is_idle_exempt ? Infinity : user.is_kiosk ? 8 * 60 * 60 * 1000 : 5 * 60 * 1000
    const refreshIntervalMs = 60 * 1000
    let lastActivity = Date.now()
    let lastRefresh = 0

    const onActivity = () => {
      lastActivity = Date.now()
    }
    const activityEvents = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll']
    activityEvents.forEach((evt) => window.addEventListener(evt, onActivity, { passive: true }))

    const checkIdle = setInterval(() => {
      const now = Date.now()
      const idleFor = now - lastActivity
      if (idleFor > idleTimeoutMs) {
        logout()
        window.location.href = '/login'
        return
      }
      if (now - lastRefresh > refreshIntervalMs) {
        lastRefresh = now
        api.post('/auth/refresh')
          .then(({ data }) => localStorage.setItem('token', data.access_token))
          .catch(() => {})
      }
    }, 10 * 1000)

    return () => {
      activityEvents.forEach((evt) => window.removeEventListener(evt, onActivity))
      clearInterval(checkIdle)
    }
  }, [user])

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, loginWithGoogle, markTourSeen, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
