import { useEffect, useState } from 'react'
import { Shield, Trash2, UserCog, CheckCircle, Monitor, RefreshCw, Download, Copy, Pencil, Ban, Infinity as InfinityIcon } from 'lucide-react'
import axios from 'axios'
import api from '../api/client'
import { getBugReports, resolveBugReport } from '../api/collection'
import { getCardGames } from '../api/cards'
import type { BugReport, CardGame, KioskSearchLog, KioskSettings, KioskSignup } from '../types'
import EditSignupModal from '../components/Admin/EditSignupModal'

// A full-catalog sync is many sequential apitcg.com calls proxied through
// tcg-scraper, plus a DB upsert per card - at the 60/min rate limit, ~280
// calls alone is ~4.7 minutes for all of Pokemon, before upsert overhead.
// Generous headroom rather than the axios default; if you're behind a
// reverse proxy in production (e.g. Caddy), it needs a matching timeout on
// this route too, or it'll cut the request before this client-side timeout
// ever fires.
const FULL_SYNC_TIMEOUT_MS = 20 * 60 * 1000

interface AdminUser {
  id: number
  username: string
  is_admin: boolean
  is_kiosk: boolean
  is_suspended: boolean
  is_idle_exempt: boolean
  created_at: string
}

interface PublisherMismatch {
  local_publisher: string
  comic_count: number
  suggested_publisher: string | null
}

interface PublisherMergeSkip {
  local_publisher: string
  reason: string
}

interface PublisherMergeResult {
  merged_comics: number
  skipped: PublisherMergeSkip[]
}

interface UpcIssue {
  comic_id: number
  series: string
  issue_number: string | null
  publisher: string | null
  upc: string
  suggested_upc: string | null
}

interface LegacyNumberIssue {
  comic_id: number
  series: string
  issue_number: string
  publisher: string | null
  suggested_issue_number: string
  suggested_legacy_number: string
}

interface ComicVineSeriesSyncResult {
  query: string
  status: 'synced' | 'not_found'
  matched_series: string | null
  publisher: string | null
  total_issues: number | null
  issues_with_image: number | null
  created: number | null
  images_filled: number | null
  skipped: number | null
}

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [reports, setReports] = useState<BugReport[]>([])
  const [showResolved, setShowResolved] = useState(false)
  const [tab, setTab] = useState<'users' | 'bugs' | 'cards' | 'signups' | 'searches' | 'settings' | 'publishers' | 'upc' | 'legacy' | 'comicvine'>('users')
  const [loading, setLoading] = useState(true)
  const [signups, setSignups] = useState<KioskSignup[]>([])
  const [emailsCopied, setEmailsCopied] = useState(false)
  const [signupSearch, setSignupSearch] = useState('')
  const [editingSignup, setEditingSignup] = useState<KioskSignup | null>(null)
  const [searchLogs, setSearchLogs] = useState<KioskSearchLog[]>([])
  const [searchLogFilter, setSearchLogFilter] = useState('')

  const [kioskSettings, setKioskSettings] = useState<KioskSettings | null>(null)
  const [savingSettings, setSavingSettings] = useState(false)
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null)
  const [settingsError, setSettingsError] = useState('')

  const [cardGames, setCardGames] = useState<CardGame[]>([])
  const [selectedGameSlug, setSelectedGameSlug] = useState('')
  const [syncingGames, setSyncingGames] = useState(false)
  const [syncingSets, setSyncingSets] = useState(false)
  const [syncingProducts, setSyncingProducts] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)
  const [syncError, setSyncError] = useState('')

  const [comicvineNames, setComicvineNames] = useState('')
  const [syncingComicvine, setSyncingComicvine] = useState(false)
  const [comicvineResults, setComicvineResults] = useState<ComicVineSeriesSyncResult[]>([])
  const [comicvineRateLimited, setComicvineRateLimited] = useState(false)
  const [comicvineError, setComicvineError] = useState('')

  const [publisherMismatches, setPublisherMismatches] = useState<PublisherMismatch[]>([])
  const [mismatchesLoading, setMismatchesLoading] = useState(true)
  const [mismatchesError, setMismatchesError] = useState('')
  const [targetEdits, setTargetEdits] = useState<Record<string, string>>({})
  const [selectedMismatches, setSelectedMismatches] = useState<Set<string>>(new Set())
  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState<PublisherMergeResult | null>(null)
  const [applyError, setApplyError] = useState('')

  useEffect(() => {
    api.get<AdminUser[]>('/admin/users').then(r => { setUsers(r.data); setLoading(false) })
  }, [])

  useEffect(() => {
    api.get<KioskSignup[]>('/admin/kiosk-signups').then(r => setSignups(r.data))
  }, [])

  useEffect(() => {
    api.get<KioskSearchLog[]>('/admin/kiosk-searches').then(r => setSearchLogs(r.data))
  }, [])

  useEffect(() => {
    api.get<KioskSettings>('/admin/kiosk-settings').then(r => setKioskSettings(r.data))
  }, [])

  const loadPublisherMismatches = () => {
    setMismatchesLoading(true)
    setMismatchesError('')
    api.get<PublisherMismatch[]>('/admin/publisher-mismatches')
      .then(r => {
        setPublisherMismatches(r.data)
        // Pre-fill each row's editable target with its suggestion (if any),
        // but only the first time we see that local_publisher - don't clobber
        // an admin's in-progress manual edit on a refetch after applying others.
        setTargetEdits(prev => {
          const next = { ...prev }
          r.data.forEach(m => {
            if (!(m.local_publisher in next)) next[m.local_publisher] = m.suggested_publisher ?? ''
          })
          return next
        })
      })
      .catch((e: unknown) => {
        const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
        setMismatchesError(detail || 'Failed to load publisher report.')
      })
      .finally(() => setMismatchesLoading(false))
  }

  useEffect(() => { loadPublisherMismatches() }, [])

  const toggleMismatchSelected = (local: string) => {
    setSelectedMismatches(prev => {
      const next = new Set(prev)
      next.has(local) ? next.delete(local) : next.add(local)
      return next
    })
  }

  const selectAllWithTarget = () => {
    setSelectedMismatches(new Set(
      publisherMismatches.filter(m => targetEdits[m.local_publisher]?.trim()).map(m => m.local_publisher),
    ))
  }

  const applyPublisherMerges = async () => {
    const updates = Array.from(selectedMismatches)
      .map(local => ({ local_publisher: local, target_publisher: (targetEdits[local] ?? '').trim() }))
      .filter(u => u.target_publisher)
    if (!updates.length) return
    setApplying(true)
    setApplyResult(null)
    setApplyError('')
    try {
      const { data } = await api.post<PublisherMergeResult>('/admin/publisher-mismatches/apply', { updates })
      setApplyResult(data)
      setSelectedMismatches(new Set())
      loadPublisherMismatches()
    } catch (e: unknown) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setApplyError(detail || 'Failed to apply publisher merges.')
    } finally {
      setApplying(false)
    }
  }

  const [upcIssues, setUpcIssues] = useState<UpcIssue[]>([])
  const [upcIssuesLoading, setUpcIssuesLoading] = useState(true)
  const [upcIssuesError, setUpcIssuesError] = useState('')
  const [fixingUpcId, setFixingUpcId] = useState<number | null>(null)
  const [upcFixErrors, setUpcFixErrors] = useState<Record<number, string>>({})

  const loadUpcIssues = () => {
    setUpcIssuesLoading(true)
    setUpcIssuesError('')
    api.get<UpcIssue[]>('/admin/upc-issues')
      .then(r => setUpcIssues(r.data))
      .catch((e: unknown) => {
        const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
        setUpcIssuesError(detail || 'Failed to load UPC report.')
      })
      .finally(() => setUpcIssuesLoading(false))
  }

  useEffect(() => { loadUpcIssues() }, [])

  const fixUpcIssue = async (comicId: number) => {
    setFixingUpcId(comicId)
    setUpcFixErrors(prev => { const next = { ...prev }; delete next[comicId]; return next })
    try {
      await api.post(`/admin/upc-issues/${comicId}/fix`)
      setUpcIssues(prev => prev.filter(i => i.comic_id !== comicId))
    } catch (e: unknown) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setUpcFixErrors(prev => ({ ...prev, [comicId]: detail || 'Failed to fix this UPC.' }))
    } finally {
      setFixingUpcId(null)
    }
  }

  const [legacyIssues, setLegacyIssues] = useState<LegacyNumberIssue[]>([])
  const [legacyIssuesLoading, setLegacyIssuesLoading] = useState(true)
  const [legacyIssuesError, setLegacyIssuesError] = useState('')
  const [fixingLegacyId, setFixingLegacyId] = useState<number | null>(null)
  const [legacyFixErrors, setLegacyFixErrors] = useState<Record<number, string>>({})

  const loadLegacyIssues = () => {
    setLegacyIssuesLoading(true)
    setLegacyIssuesError('')
    api.get<LegacyNumberIssue[]>('/admin/legacy-numbers')
      .then(r => setLegacyIssues(r.data))
      .catch((e: unknown) => {
        const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
        setLegacyIssuesError(detail || 'Failed to load legacy number report.')
      })
      .finally(() => setLegacyIssuesLoading(false))
  }

  useEffect(() => { loadLegacyIssues() }, [])

  const fixLegacyIssue = async (comicId: number) => {
    setFixingLegacyId(comicId)
    setLegacyFixErrors(prev => { const next = { ...prev }; delete next[comicId]; return next })
    try {
      await api.post(`/admin/legacy-numbers/${comicId}/fix`)
      setLegacyIssues(prev => prev.filter(i => i.comic_id !== comicId))
    } catch (e: unknown) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setLegacyFixErrors(prev => ({ ...prev, [comicId]: detail || 'Failed to fix this issue number.' }))
    } finally {
      setFixingLegacyId(null)
    }
  }

  const updateSettingsField = (key: keyof KioskSettings, value: number) => {
    setKioskSettings(prev => prev ? { ...prev, [key]: value } : prev)
  }

  const saveKioskSettings = async () => {
    if (!kioskSettings) return
    setSavingSettings(true)
    setSettingsMessage(null)
    setSettingsError('')
    try {
      const { data } = await api.patch<KioskSettings>('/admin/kiosk-settings', kioskSettings)
      setKioskSettings(data)
      setSettingsMessage('Saved.')
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
      setSettingsError(typeof detail === 'string' ? detail : 'Failed to save settings.')
    } finally {
      setSavingSettings(false)
    }
  }

  const downloadSignupsCsv = () => {
    const header = ['First Name', 'Last Name', 'Email', 'Phone', 'Notes', 'Signed Up']
    const rows = signups.map(s => [
      s.first_name, s.last_name, s.email, s.phone ?? '', s.notes ?? '', new Date(s.created_at).toLocaleDateString(),
    ])
    const escape = (v: string) => `"${v.replace(/"/g, '""')}"`
    const csv = [header, ...rows].map(row => row.map(escape).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `kiosk-signups-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const copySignupEmails = async () => {
    const emails = filteredSignups.map(s => s.email).join(', ')
    await navigator.clipboard.writeText(emails)
    setEmailsCopied(true)
    setTimeout(() => setEmailsCopied(false), 2000)
  }

  const filteredSignups = signupSearch.trim()
    ? signups.filter(s => {
        const q = signupSearch.trim().toLowerCase()
        return (
          `${s.first_name} ${s.last_name}`.toLowerCase().includes(q) ||
          s.email.toLowerCase().includes(q) ||
          (s.phone ?? '').toLowerCase().includes(q) ||
          (s.notes ?? '').toLowerCase().includes(q)
        )
      })
    : signups

  const filteredSearchLogs = searchLogFilter.trim()
    ? searchLogs.filter(l => l.query.toLowerCase().includes(searchLogFilter.trim().toLowerCase()))
    : searchLogs

  const handleDeleteSignup = async (signup: KioskSignup) => {
    if (!confirm(`Delete signup for ${signup.first_name} ${signup.last_name} (${signup.email})?`)) return
    await api.delete(`/admin/kiosk-signups/${signup.id}`)
    setSignups(prev => prev.filter(s => s.id !== signup.id))
  }

  useEffect(() => {
    getBugReports(showResolved ? undefined : false).then(setReports)
  }, [showResolved])

  const refreshCardGames = () => getCardGames().then(games => {
    setCardGames(games)
    if (games.length && !selectedGameSlug) setSelectedGameSlug(games[0].slug)
  })

  useEffect(() => { refreshCardGames() }, [])

  const syncErrorDetail = (err: unknown, fallback: string) =>
    (axios.isAxiosError(err) ? err.response?.data?.detail : null) || fallback

  const handleSyncGames = async () => {
    setSyncingGames(true)
    setSyncError('')
    setSyncMessage(null)
    try {
      const { data } = await api.post<{ synced: number }>('/admin/cards/sync/games')
      await refreshCardGames()
      setSyncMessage(`Synced ${data.synced} game${data.synced === 1 ? '' : 's'}.`)
    } catch (err) {
      setSyncError(syncErrorDetail(err, 'Failed to sync games.'))
    } finally {
      setSyncingGames(false)
    }
  }

  const handleSyncSets = async () => {
    if (!selectedGameSlug) return
    setSyncingSets(true)
    setSyncError('')
    setSyncMessage(null)
    try {
      const { data } = await api.post<{ synced: number }>('/admin/cards/sync/sets', undefined, {
        params: { game_slug: selectedGameSlug },
      })
      setSyncMessage(`Synced ${data.synced} set${data.synced === 1 ? '' : 's'} for ${selectedGameSlug}.`)
    } catch (err) {
      setSyncError(syncErrorDetail(err, 'Failed to sync sets.'))
    } finally {
      setSyncingSets(false)
    }
  }

  const handleSyncAllProducts = async () => {
    if (!selectedGameSlug) return
    if (!confirm(
      `Sync the entire "${selectedGameSlug}" catalog now? This can take several minutes and counts ` +
      'against your apitcg.com monthly call quota - see tcg-scraper/README.md for the cost (~280 calls ' +
      'for all of Pokemon). Do not close this page while it runs.'
    )) return
    setSyncingProducts(true)
    setSyncError('')
    setSyncMessage(null)
    try {
      const { data } = await api.post<{ synced: number; pages: number }>(
        '/admin/cards/sync/products/all',
        undefined,
        { params: { game_slug: selectedGameSlug }, timeout: FULL_SYNC_TIMEOUT_MS },
      )
      setSyncMessage(`Synced ${data.synced} card${data.synced === 1 ? '' : 's'} across ${data.pages} page(s) for ${selectedGameSlug}.`)
    } catch (err) {
      setSyncError(syncErrorDetail(err, 'Failed to sync the catalog.'))
    } finally {
      setSyncingProducts(false)
    }
  }

  const handleSyncComicvine = async () => {
    const names = comicvineNames.split('\n').map(n => n.trim()).filter(Boolean)
    if (names.length === 0) return
    setSyncingComicvine(true)
    setComicvineError('')
    setComicvineResults([])
    setComicvineRateLimited(false)
    try {
      const { data } = await api.post<{ results: ComicVineSeriesSyncResult[]; rate_limited: boolean }>(
        '/admin/comicvine/sync-series',
        { names },
        { timeout: FULL_SYNC_TIMEOUT_MS },
      )
      setComicvineResults(data.results)
      setComicvineRateLimited(data.rate_limited)
    } catch (err) {
      setComicvineError(syncErrorDetail(err, 'Failed to sync from ComicVine.'))
    } finally {
      setSyncingComicvine(false)
    }
  }

  const toggleAdmin = async (user: AdminUser) => {
    await api.patch(`/admin/users/${user.id}`, { is_admin: !user.is_admin })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_admin: !u.is_admin } : u))
  }

  const toggleKiosk = async (user: AdminUser) => {
    await api.patch(`/admin/users/${user.id}`, { is_kiosk: !user.is_kiosk })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_kiosk: !u.is_kiosk } : u))
  }

  const toggleSuspend = async (user: AdminUser) => {
    const next = !user.is_suspended
    if (next && !confirm(`Suspend ${user.username}? They'll be logged out immediately and unable to sign back in until unsuspended.`)) return
    await api.patch(`/admin/users/${user.id}`, { is_suspended: next })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_suspended: next } : u))
  }

  const toggleIdleExempt = async (user: AdminUser) => {
    const next = !user.is_idle_exempt
    await api.patch(`/admin/users/${user.id}`, { is_idle_exempt: next })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_idle_exempt: next } : u))
  }

  const deleteUser = async (user: AdminUser) => {
    if (!confirm(`Delete user ${user.username}? This cannot be undone.`)) return
    await api.delete(`/admin/users/${user.id}`)
    setUsers(prev => prev.filter(u => u.id !== user.id))
  }

  const handleResolve = async (id: number) => {
    await resolveBugReport(id)
    if (!showResolved) {
      setReports(prev => prev.filter(r => r.id !== id))
    } else {
      setReports(prev => prev.map(r => r.id === id ? { ...r, resolved: true } : r))
    }
  }

  const unresolvedCount = reports.filter(r => !r.resolved).length

  const roleLabel = (user: AdminUser) => {
    if (user.is_admin) return { label: 'Admin', cls: 'bg-yellow-500/20 text-yellow-400' }
    if (user.is_kiosk) return { label: 'Kiosk', cls: 'bg-blue-500/20 text-blue-400' }
    return { label: 'User', cls: 'bg-gray-700 text-gray-400' }
  }

  const TABS = ['users', 'bugs', 'cards', 'signups', 'searches', 'settings', 'publishers', 'upc', 'legacy', 'comicvine'] as const

  const tabLabel = (t: typeof TABS[number]) => (
    t === 'users' ? `Users (${users.length})`
    : t === 'bugs' ? `Bug Reports${unresolvedCount ? ` (${unresolvedCount})` : ''}`
    : t === 'cards' ? 'Cards Sync'
    : t === 'signups' ? `Kiosk Signups (${signups.length})`
    : t === 'searches' ? 'Kiosk Searches'
    : t === 'settings' ? 'Kiosk Settings'
    : t === 'publishers' ? `Publishers${publisherMismatches.length ? ` (${publisherMismatches.length})` : ''}`
    : t === 'upc' ? `UPC Issues${upcIssues.length ? ` (${upcIssues.length})` : ''}`
    : t === 'legacy' ? `Legacy Numbers${legacyIssues.length ? ` (${legacyIssues.length})` : ''}`
    : 'ComicVine Images'
  )

  return (
    <div className="max-w-6xl mx-auto px-3 sm:px-4 py-6 sm:py-8">
      <div className="flex items-center gap-3 mb-6 sm:mb-8">
        <Shield size={24} className="text-yellow-400 flex-shrink-0" />
        <h1 className="text-xl sm:text-2xl font-bold">Admin Dashboard</h1>
      </div>

      <select
        value={tab}
        onChange={e => setTab(e.target.value as typeof tab)}
        className="md:hidden w-full mb-6 bg-gray-900 border border-gray-800 rounded-xl px-3 py-2.5 text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        {TABS.map(t => (
          <option key={t} value={t}>{tabLabel(t)}</option>
        ))}
      </select>

      <div className="md:flex md:items-start md:gap-6">
        <nav className="hidden md:block md:w-44 lg:w-56 flex-shrink-0 sticky top-6 space-y-1">
          {TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`w-full text-left px-3 py-2 text-sm font-medium rounded-lg transition ${tab === t ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}`}
            >
              {tabLabel(t)}
            </button>
          ))}
        </nav>

        <div className="flex-1 min-w-0">
        {tab === 'users' && (
          <div>
            {loading ? (
              <div className="text-center text-gray-400 py-12">Loading…</div>
            ) : (
              <>
                <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-3">
                  {users.map(user => {
                    const role = roleLabel(user)
                    return (
                      <div key={user.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="font-medium text-white truncate">{user.username}</p>
                          <div className="flex-shrink-0 flex items-center gap-1.5">
                            {user.is_suspended && (
                              <span className="text-xs font-medium px-2 py-1 rounded-full bg-red-500/20 text-red-400">
                                Suspended
                              </span>
                            )}
                            <span className={`text-xs font-medium px-2 py-1 rounded-full ${role.cls}`}>
                              {role.label}
                            </span>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500 mt-1 mb-3">Joined {new Date(user.created_at).toLocaleDateString()}</p>
                        <div className="flex items-center gap-1 -ml-2">
                          <button
                            onClick={() => toggleAdmin(user)}
                            title={user.is_admin ? 'Revoke admin' : 'Make admin'}
                            className="p-2 rounded-lg text-gray-400 hover:text-yellow-400 hover:bg-gray-800 transition"
                          >
                            <UserCog size={16} />
                          </button>
                          <button
                            onClick={() => toggleKiosk(user)}
                            title={user.is_kiosk ? 'Disable kiosk' : 'Enable kiosk'}
                            className={`p-2 rounded-lg hover:bg-gray-800 transition ${user.is_kiosk ? 'text-blue-400' : 'text-gray-400 hover:text-blue-400'}`}
                          >
                            <Monitor size={16} />
                          </button>
                          <button
                            onClick={() => toggleSuspend(user)}
                            title={user.is_suspended ? 'Unsuspend user' : 'Suspend user (forces logout)'}
                            className={`p-2 rounded-lg hover:bg-gray-800 transition ${user.is_suspended ? 'text-red-400' : 'text-gray-400 hover:text-red-400'}`}
                          >
                            <Ban size={16} />
                          </button>
                          <button
                            onClick={() => toggleIdleExempt(user)}
                            title={user.is_idle_exempt ? 'Re-enable 5-min idle logout' : 'Exempt from idle logout (testing)'}
                            className={`p-2 rounded-lg hover:bg-gray-800 transition ${user.is_idle_exempt ? 'text-green-400' : 'text-gray-400 hover:text-green-400'}`}
                          >
                            <InfinityIcon size={16} />
                          </button>
                          <button onClick={() => deleteUser(user)} title="Delete user" className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-gray-800 transition">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div className="hidden lg:block bg-gray-900 rounded-2xl border border-gray-800 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                      <tr>
                        <th className="px-6 py-3 text-left">Username</th>
                        <th className="px-6 py-3 text-left">Role</th>
                        <th className="px-6 py-3 text-left">Joined</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {users.map(user => {
                        const role = roleLabel(user)
                        return (
                          <tr key={user.id} className="hover:bg-gray-800/50 transition">
                            <td className="px-6 py-4">{user.username}</td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-1.5">
                                {user.is_suspended && (
                                  <span className="text-xs font-medium px-2 py-1 rounded-full bg-red-500/20 text-red-400">
                                    Suspended
                                  </span>
                                )}
                                <span className={`text-xs font-medium px-2 py-1 rounded-full ${role.cls}`}>
                                  {role.label}
                                </span>
                              </div>
                            </td>
                            <td className="px-6 py-4 text-gray-400">{new Date(user.created_at).toLocaleDateString()}</td>
                            <td className="px-6 py-4 text-right">
                              <div className="flex justify-end gap-2">
                                <button
                                  onClick={() => toggleAdmin(user)}
                                  title={user.is_admin ? 'Revoke admin' : 'Make admin'}
                                  className="p-2 rounded-lg text-gray-400 hover:text-yellow-400 hover:bg-gray-700 transition"
                                >
                                  <UserCog size={16} />
                                </button>
                                <button
                                  onClick={() => toggleKiosk(user)}
                                  title={user.is_kiosk ? 'Disable kiosk' : 'Enable kiosk'}
                                  className={`p-2 rounded-lg hover:bg-gray-700 transition ${user.is_kiosk ? 'text-blue-400' : 'text-gray-400 hover:text-blue-400'}`}
                                >
                                  <Monitor size={16} />
                                </button>
                                <button
                                  onClick={() => toggleSuspend(user)}
                                  title={user.is_suspended ? 'Unsuspend user' : 'Suspend user (forces logout)'}
                                  className={`p-2 rounded-lg hover:bg-gray-700 transition ${user.is_suspended ? 'text-red-400' : 'text-gray-400 hover:text-red-400'}`}
                                >
                                  <Ban size={16} />
                                </button>
                                <button
                                  onClick={() => toggleIdleExempt(user)}
                                  title={user.is_idle_exempt ? 'Re-enable 5-min idle logout' : 'Exempt from idle logout (testing)'}
                                  className={`p-2 rounded-lg hover:bg-gray-700 transition ${user.is_idle_exempt ? 'text-green-400' : 'text-gray-400 hover:text-green-400'}`}
                                >
                                  <InfinityIcon size={16} />
                                </button>
                                <button onClick={() => deleteUser(user)} title="Delete user" className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-gray-700 transition">
                                  <Trash2 size={16} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'bugs' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-gray-400">{reports.length} report{reports.length !== 1 ? 's' : ''}</p>
              <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                <input type="checkbox" checked={showResolved} onChange={e => setShowResolved(e.target.checked)} className="w-3.5 h-3.5 rounded accent-brand-500" />
                Show resolved
              </label>
            </div>

            {reports.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No bug reports.</div>
            ) : (
              <div className="space-y-3">
                {reports.map(r => (
                  <div key={r.id} className={`bg-gray-900 border rounded-xl p-4 ${r.resolved ? 'border-gray-800 opacity-50' : 'border-gray-700'}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-1.5">
                          <span className="text-xs font-medium text-gray-400">{r.user_username}</span>
                          {r.comic_name && <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded">re: {r.comic_name}</span>}
                          {r.page_url && <span className="text-xs text-gray-600">{r.page_url}</span>}
                          <span className="text-xs text-gray-600">{new Date(r.created_at).toLocaleDateString()}</span>
                          {r.resolved && <span className="text-xs text-green-600">Resolved</span>}
                        </div>
                        <p className="text-sm text-gray-200">{r.text}</p>
                      </div>
                      {!r.resolved && (
                        <button onClick={() => handleResolve(r.id)} title="Mark resolved" className="flex-shrink-0 p-1.5 text-gray-400 hover:text-green-400 hover:bg-gray-700 rounded-lg transition">
                          <CheckCircle size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'cards' && (
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6 space-y-6">
            <div>
              <p className="text-sm text-gray-300 mb-1">Step 1 - Games</p>
              <p className="text-xs text-gray-500 mb-3">Pulls every TCG apitcg.com knows about (Pokemon, Magic, One Piece, etc.) - cheap, one call.</p>
              <button
                onClick={handleSyncGames}
                disabled={syncingGames}
                className="flex items-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm font-medium rounded-lg transition disabled:opacity-50"
              >
                <RefreshCw size={14} className={syncingGames ? 'animate-spin' : ''} />
                {syncingGames ? 'Syncing…' : 'Sync Games'}
              </button>
            </div>

            <div className="pt-4 border-t border-gray-800">
              <p className="text-sm text-gray-300 mb-1">Step 2 - Pick a game</p>
              {cardGames.length === 0 ? (
                <p className="text-xs text-gray-500">No games synced yet - run Step 1 first.</p>
              ) : (
                <select
                  value={selectedGameSlug}
                  onChange={e => setSelectedGameSlug(e.target.value)}
                  className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {cardGames.map(g => (
                    <option key={g.slug} value={g.slug}>{g.name}</option>
                  ))}
                </select>
              )}
            </div>

            <div className="pt-4 border-t border-gray-800">
              <p className="text-sm text-gray-300 mb-1">Step 3 - Sets (optional)</p>
              <p className="text-xs text-gray-500 mb-3">Fills in set logo/symbol images and printed totals - not required before syncing cards below, since each card carries its own set info too.</p>
              <button
                onClick={handleSyncSets}
                disabled={syncingSets || !selectedGameSlug}
                className="flex items-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm font-medium rounded-lg transition disabled:opacity-50"
              >
                <RefreshCw size={14} className={syncingSets ? 'animate-spin' : ''} />
                {syncingSets ? 'Syncing…' : 'Sync Sets'}
              </button>
            </div>

            <div className="pt-4 border-t border-gray-800">
              <p className="text-sm text-gray-300 mb-1">Step 4 - Full catalog</p>
              <p className="text-xs text-gray-500 mb-3">
                Syncs every card for the selected game in one paginated pass. Counts against your apitcg.com
                monthly quota (1,000 free-tier calls/month) - roughly 280 calls for all of Pokemon. Safe to
                re-run (upserts, no duplicates), but re-running re-spends the same quota.
              </p>
              <button
                onClick={handleSyncAllProducts}
                disabled={syncingProducts || !selectedGameSlug}
                className="flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
              >
                <RefreshCw size={14} className={syncingProducts ? 'animate-spin' : ''} />
                {syncingProducts ? 'Syncing full catalog… this can take several minutes' : 'Sync Full Catalog'}
              </button>
            </div>

            {syncMessage && <p className="text-green-400 text-sm">{syncMessage}</p>}
            {syncError && <p className="text-red-400 text-sm">{syncError}</p>}
          </div>
        )}

        {tab === 'signups' && (
          <div>
            <div className="flex flex-col gap-3 mb-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                <p className="text-sm text-gray-400 whitespace-nowrap">
                  {signupSearch.trim()
                    ? `${filteredSignups.length} of ${signups.length} signup${signups.length !== 1 ? 's' : ''}`
                    : `${signups.length} signup${signups.length !== 1 ? 's' : ''}`}
                </p>
                <input
                  value={signupSearch}
                  onChange={e => setSignupSearch(e.target.value)}
                  placeholder="Search name, email, phone, notes…"
                  className="w-full sm:w-56 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copySignupEmails}
                  disabled={filteredSignups.length === 0}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm font-medium rounded-lg transition disabled:opacity-50"
                >
                  <Copy size={14} />
                  {emailsCopied ? 'Copied!' : 'Copy Emails'}
                </button>
                <button
                  onClick={downloadSignupsCsv}
                  disabled={signups.length === 0}
                  className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm font-medium rounded-lg transition disabled:opacity-50"
                >
                  <Download size={14} />
                  Download CSV
                </button>
              </div>
            </div>

            {signups.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No kiosk signups yet.</div>
            ) : filteredSignups.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No signups match "{signupSearch.trim()}".</div>
            ) : (
              <>
                <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-3">
                  {filteredSignups.map(s => (
                    <div key={s.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-medium text-white truncate">{s.first_name} {s.last_name}</p>
                          <p className="text-sm text-gray-300 truncate">{s.email}</p>
                        </div>
                        <div className="flex-shrink-0 flex items-center gap-1 -mr-1.5">
                          <button
                            onClick={() => setEditingSignup(s)}
                            title="Edit"
                            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition"
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            onClick={() => handleDeleteSignup(s)}
                            title="Delete"
                            className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded-lg transition"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                      <div className="text-xs text-gray-400 mt-2 space-y-0.5">
                        <p>{s.phone ?? 'No phone'} · {new Date(s.created_at).toLocaleDateString()}</p>
                        {s.notes && <p className="text-gray-500">{s.notes}</p>}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="hidden lg:block bg-gray-900 rounded-2xl border border-gray-800 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                      <tr>
                        <th className="px-6 py-3 text-left">Name</th>
                        <th className="px-6 py-3 text-left">Email</th>
                        <th className="px-6 py-3 text-left">Phone</th>
                        <th className="px-6 py-3 text-left">Notes</th>
                        <th className="px-6 py-3 text-left">Signed Up</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {filteredSignups.map(s => (
                        <tr key={s.id} className="hover:bg-gray-800/50 transition">
                          <td className="px-6 py-4">{s.first_name} {s.last_name}</td>
                          <td className="px-6 py-4 text-gray-300">{s.email}</td>
                          <td className="px-6 py-4 text-gray-400">{s.phone ?? '—'}</td>
                          <td className="px-6 py-4 text-gray-400 max-w-xs truncate" title={s.notes ?? undefined}>{s.notes ?? '—'}</td>
                          <td className="px-6 py-4 text-gray-400">{new Date(s.created_at).toLocaleDateString()}</td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => setEditingSignup(s)}
                                title="Edit"
                                className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition"
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                onClick={() => handleDeleteSignup(s)}
                                title="Delete"
                                className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded-lg transition"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'searches' && (
          <div>
            <div className="flex flex-col gap-2 mb-4 sm:flex-row sm:items-center sm:gap-3">
              <p className="text-sm text-gray-400 whitespace-nowrap">
                {searchLogFilter.trim()
                  ? `${filteredSearchLogs.length} of ${searchLogs.length} search${searchLogs.length !== 1 ? 'es' : ''}`
                  : `${searchLogs.length} search${searchLogs.length !== 1 ? 'es' : ''}`}
              </p>
              <input
                value={searchLogFilter}
                onChange={e => setSearchLogFilter(e.target.value)}
                placeholder="Search queries…"
                className="w-full sm:w-56 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {searchLogs.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No kiosk searches logged yet.</div>
            ) : filteredSearchLogs.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No searches match "{searchLogFilter.trim()}".</div>
            ) : (
              <>
                <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-2">
                  {filteredSearchLogs.map(log => (
                    <div key={log.id} className="bg-gray-900 border border-gray-800 rounded-xl p-3.5">
                      <p className="text-white break-words">{log.query}</p>
                      <p className="text-xs text-gray-500 mt-1 capitalize">{log.section} · {new Date(log.created_at).toLocaleString()}</p>
                    </div>
                  ))}
                </div>

                <div className="hidden lg:block bg-gray-900 rounded-2xl border border-gray-800 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                      <tr>
                        <th className="px-6 py-3 text-left">Query</th>
                        <th className="px-6 py-3 text-left">Section</th>
                        <th className="px-6 py-3 text-left">Searched</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {filteredSearchLogs.map(log => (
                        <tr key={log.id} className="hover:bg-gray-800/50 transition">
                          <td className="px-6 py-4">{log.query}</td>
                          <td className="px-6 py-4 text-gray-400 capitalize">{log.section}</td>
                          <td className="px-6 py-4 text-gray-400">{new Date(log.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'settings' && (
          <div className="space-y-6">
            {!kioskSettings ? (
              <div className="text-center text-gray-400 py-12">Loading…</div>
            ) : (
              <>
                <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6">
                  <p className="text-sm text-gray-300 mb-4">General</p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Featured items per section</label>
                      <input
                        type="number" min={1} max={200} step={1}
                        value={kioskSettings.featured_limit}
                        onChange={e => updateSettingsField('featured_limit', Number(e.target.value))}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-3">
                    Number of books/cards shown in each featured section (Today's Picks, Signed, Graded). Shared across all four sections. Range: 1–200.
                  </p>
                </div>

                <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6">
                  <p className="text-sm text-gray-300 mb-4">Comics</p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Today's Picks price threshold ($)</label>
                      <input
                        type="number" min={0} step="0.01"
                        value={kioskSettings.comics_price_threshold}
                        onChange={e => updateSettingsField('comics_price_threshold', Number(e.target.value))}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Today's Picks refresh (minutes)</label>
                      <input
                        type="number" min={10} max={1440} step={10}
                        value={kioskSettings.todays_picks_refresh_minutes}
                        onChange={e => updateSettingsField('todays_picks_refresh_minutes', Number(e.target.value))}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Signed Comics refresh (minutes)</label>
                      <input
                        type="number" min={10} max={1440} step={10}
                        value={kioskSettings.signed_refresh_minutes}
                        onChange={e => updateSettingsField('signed_refresh_minutes', Number(e.target.value))}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-3">Refresh intervals: 10–1440 minutes (up to 24 hours).</p>
                </div>

                <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6">
                  <p className="text-sm text-gray-300 mb-4">Cards</p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Today's Picks price threshold ($)</label>
                      <input
                        type="number" min={0} step="0.01"
                        value={kioskSettings.cards_price_threshold}
                        onChange={e => updateSettingsField('cards_price_threshold', Number(e.target.value))}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Today's Picks refresh (minutes)</label>
                      <input
                        type="number" min={10} max={1440} step={10}
                        value={kioskSettings.cards_todays_picks_refresh_minutes}
                        onChange={e => updateSettingsField('cards_todays_picks_refresh_minutes', Number(e.target.value))}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Graded Cards refresh (minutes)</label>
                      <input
                        type="number" min={10} max={1440} step={10}
                        value={kioskSettings.cards_graded_refresh_minutes}
                        onChange={e => updateSettingsField('cards_graded_refresh_minutes', Number(e.target.value))}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-3">Refresh intervals: 10–1440 minutes (up to 24 hours).</p>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={saveKioskSettings}
                    disabled={savingSettings}
                    className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                  >
                    {savingSettings ? 'Saving…' : 'Save Settings'}
                  </button>
                  {settingsMessage && <p className="text-green-400 text-sm">{settingsMessage}</p>}
                  {settingsError && <p className="text-red-400 text-sm">{settingsError}</p>}
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'publishers' && (
          <div>
            <p className="text-sm text-gray-400 mb-4">
              Locally-used publisher names that don't exactly match GCD's canonical spelling for that publisher — e.g. "DC" vs "DC Comics". Applying a fix merges those comics into the correctly-named catalog entry (same merge-safe behavior as editing a comic's publisher directly).
            </p>

            {mismatchesLoading ? (
              <div className="text-center text-gray-500 py-12">Loading…</div>
            ) : mismatchesError ? (
              <div className="text-center py-12">
                <p className="text-red-400">{mismatchesError}</p>
                <button
                  onClick={loadPublisherMismatches}
                  className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
                >
                  Retry
                </button>
              </div>
            ) : publisherMismatches.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No publisher naming mismatches found.</div>
            ) : (
              <>
                <div className="flex items-center gap-4 mb-3">
                  <button type="button" onClick={selectAllWithTarget} className="text-sm text-brand-400 hover:text-brand-300 transition">
                    Select all with a target ({publisherMismatches.filter(m => targetEdits[m.local_publisher]?.trim()).length})
                  </button>
                  <button type="button" onClick={() => setSelectedMismatches(new Set())} className="text-sm text-gray-400 hover:text-white transition">
                    Clear selection
                  </button>
                </div>

                <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-3">
                  {publisherMismatches.map(m => (
                    <div key={m.local_publisher} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                      <label className="flex items-center gap-2.5">
                        <input
                          type="checkbox"
                          checked={selectedMismatches.has(m.local_publisher)}
                          onChange={() => toggleMismatchSelected(m.local_publisher)}
                          className="w-3.5 h-3.5 rounded accent-brand-500 flex-shrink-0"
                        />
                        <span className="text-gray-300 font-mono truncate">{m.local_publisher}</span>
                        <span className="flex-shrink-0 text-xs text-gray-500 ml-auto">{m.comic_count} comic{m.comic_count === 1 ? '' : 's'}</span>
                      </label>
                      <input
                        value={targetEdits[m.local_publisher] ?? ''}
                        onChange={e => setTargetEdits(prev => ({ ...prev, [m.local_publisher]: e.target.value }))}
                        placeholder={m.suggested_publisher ? undefined : 'No confident match — type one'}
                        className={`mt-2.5 w-full bg-gray-800 border rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500 ${m.suggested_publisher ? 'border-gray-700' : 'border-amber-700/50'}`}
                      />
                    </div>
                  ))}
                </div>

                <div className="hidden lg:block bg-gray-900 rounded-2xl border border-gray-800 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                      <tr>
                        <th className="px-4 py-3"></th>
                        <th className="px-4 py-3 text-left">Local Publisher</th>
                        <th className="px-4 py-3 text-left">Comics</th>
                        <th className="px-4 py-3 text-left">Target (GCD)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {publisherMismatches.map(m => (
                        <tr key={m.local_publisher} className="hover:bg-gray-800/50 transition">
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={selectedMismatches.has(m.local_publisher)}
                              onChange={() => toggleMismatchSelected(m.local_publisher)}
                              className="w-3.5 h-3.5 rounded accent-brand-500"
                            />
                          </td>
                          <td className="px-4 py-3 text-gray-300 font-mono">{m.local_publisher}</td>
                          <td className="px-4 py-3 text-gray-400">{m.comic_count}</td>
                          <td className="px-4 py-3">
                            <input
                              value={targetEdits[m.local_publisher] ?? ''}
                              onChange={e => setTargetEdits(prev => ({ ...prev, [m.local_publisher]: e.target.value }))}
                              placeholder={m.suggested_publisher ? undefined : 'No confident match — type one'}
                              className={`w-full bg-gray-800 border rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500 ${m.suggested_publisher ? 'border-gray-700' : 'border-amber-700/50'}`}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center gap-3 mt-4">
                  <button
                    onClick={applyPublisherMerges}
                    disabled={applying || selectedMismatches.size === 0}
                    className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                  >
                    {applying ? 'Applying…' : `Apply Selected (${selectedMismatches.size})`}
                  </button>
                  {applyError && <p className="text-red-400 text-sm">{applyError}</p>}
                </div>

                {applyResult && (
                  <div className="mt-4 bg-gray-900 rounded-xl border border-gray-800 p-4 text-sm">
                    <p className="text-green-400">
                      Merged {applyResult.merged_comics} comic{applyResult.merged_comics === 1 ? '' : 's'}.
                    </p>
                    {applyResult.skipped.length > 0 && (
                      <div className="mt-2">
                        <p className="text-amber-400">{applyResult.skipped.length} skipped:</p>
                        <ul className="mt-1 space-y-1 text-gray-400">
                          {applyResult.skipped.map((s, i) => (
                            <li key={i}>{s.local_publisher}: {s.reason}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {tab === 'upc' && (
          <div>
            <p className="text-sm text-gray-400 mb-4">
              Comics whose stored UPC isn't a clean 12 or 17-digit number — usually a space or dash typed/pasted between the UPC and 5-digit price add-on (GCD sometimes displays it that way). A malformed UPC will never match a clean scan again. Fixing merges into a matching catalog entry if one already exists, same as everywhere else.
            </p>

            {upcIssuesLoading ? (
              <div className="text-center text-gray-500 py-12">Loading…</div>
            ) : upcIssuesError ? (
              <div className="text-center py-12">
                <p className="text-red-400">{upcIssuesError}</p>
                <button
                  onClick={loadUpcIssues}
                  className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
                >
                  Retry
                </button>
              </div>
            ) : upcIssues.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No malformed UPCs found.</div>
            ) : (
              <>
                <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-3">
                  {upcIssues.map(i => (
                    <div key={i.comic_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                      <p className="text-gray-300">
                        {i.series}{i.issue_number ? ` #${i.issue_number}` : ''}
                        {i.publisher && <span className="text-gray-500"> ({i.publisher})</span>}
                      </p>
                      <p className="text-xs font-mono text-gray-500 mt-1">{i.upc}</p>
                      <div className="flex items-center justify-between gap-3 mt-3">
                        <div className="font-mono text-sm">
                          {i.suggested_upc ? (
                            <span className="text-gray-300">→ {i.suggested_upc}</span>
                          ) : (
                            <span className="text-amber-400 text-xs">not auto-fixable</span>
                          )}
                        </div>
                        <button
                          onClick={() => fixUpcIssue(i.comic_id)}
                          disabled={!i.suggested_upc || fixingUpcId === i.comic_id}
                          title={i.suggested_upc ? 'Fix' : 'Edit this comic manually instead'}
                          className="flex-shrink-0 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-300 rounded-lg transition disabled:opacity-40"
                        >
                          {fixingUpcId === i.comic_id ? 'Fixing…' : 'Fix'}
                        </button>
                      </div>
                      {upcFixErrors[i.comic_id] && (
                        <p className="text-xs text-red-400 mt-1">{upcFixErrors[i.comic_id]}</p>
                      )}
                    </div>
                  ))}
                </div>

                <div className="hidden lg:block bg-gray-900 rounded-2xl border border-gray-800 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                      <tr>
                        <th className="px-4 py-3 text-left">Comic</th>
                        <th className="px-4 py-3 text-left">Stored UPC</th>
                        <th className="px-4 py-3 text-left">Cleaned</th>
                        <th className="px-4 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {upcIssues.map(i => (
                        <tr key={i.comic_id} className="hover:bg-gray-800/50 transition">
                          <td className="px-4 py-3 text-gray-300">
                            {i.series}{i.issue_number ? ` #${i.issue_number}` : ''}
                            {i.publisher && <span className="text-gray-500"> ({i.publisher})</span>}
                          </td>
                          <td className="px-4 py-3 text-gray-400 font-mono">{i.upc}</td>
                          <td className="px-4 py-3 font-mono">
                            {i.suggested_upc ? (
                              <span className="text-gray-300">{i.suggested_upc}</span>
                            ) : (
                              <span className="text-amber-400">not auto-fixable</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => fixUpcIssue(i.comic_id)}
                              disabled={!i.suggested_upc || fixingUpcId === i.comic_id}
                              title={i.suggested_upc ? 'Fix' : 'Edit this comic manually instead'}
                              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-300 rounded-lg transition disabled:opacity-40"
                            >
                              {fixingUpcId === i.comic_id ? 'Fixing…' : 'Fix'}
                            </button>
                            {upcFixErrors[i.comic_id] && (
                              <p className="text-xs text-red-400 mt-1">{upcFixErrors[i.comic_id]}</p>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'legacy' && (
          <div>
            <p className="text-sm text-gray-400 mb-4">
              Comics whose issue number still has GCD's "1 (685)" format embedded — a relaunched series' new issue number plus its old "legacy" continuous number, in parentheses — instead of being split into separate Issue Number and Legacy Number fields. Fixing merges into a matching catalog entry if one already exists, same as everywhere else.
            </p>

            {legacyIssuesLoading ? (
              <div className="text-center text-gray-500 py-12">Loading…</div>
            ) : legacyIssuesError ? (
              <div className="text-center py-12">
                <p className="text-red-400">{legacyIssuesError}</p>
                <button
                  onClick={loadLegacyIssues}
                  className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
                >
                  Retry
                </button>
              </div>
            ) : legacyIssues.length === 0 ? (
              <div className="text-center text-gray-500 py-12">No embedded legacy numbers found.</div>
            ) : (
              <>
                <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-3">
                  {legacyIssues.map(i => (
                    <div key={i.comic_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                      <p className="text-gray-300">
                        {i.series} #{i.issue_number}
                        {i.publisher && <span className="text-gray-500"> ({i.publisher})</span>}
                      </p>
                      <p className="text-sm text-gray-300 mt-2">
                        → #{i.suggested_issue_number} <span className="text-gray-500">(Legacy #{i.suggested_legacy_number})</span>
                      </p>
                      <div className="flex justify-end mt-3">
                        <button
                          onClick={() => fixLegacyIssue(i.comic_id)}
                          disabled={fixingLegacyId === i.comic_id}
                          title="Fix"
                          className="flex-shrink-0 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-300 rounded-lg transition disabled:opacity-40"
                        >
                          {fixingLegacyId === i.comic_id ? 'Fixing…' : 'Fix'}
                        </button>
                      </div>
                      {legacyFixErrors[i.comic_id] && (
                        <p className="text-xs text-red-400 mt-1">{legacyFixErrors[i.comic_id]}</p>
                      )}
                    </div>
                  ))}
                </div>

                <div className="hidden lg:block bg-gray-900 rounded-2xl border border-gray-800 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                      <tr>
                        <th className="px-4 py-3 text-left">Comic</th>
                        <th className="px-4 py-3 text-left">Current Issue Number</th>
                        <th className="px-4 py-3 text-left">Split Result</th>
                        <th className="px-4 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {legacyIssues.map(i => (
                        <tr key={i.comic_id} className="hover:bg-gray-800/50 transition">
                          <td className="px-4 py-3 text-gray-300">
                            {i.series}
                            {i.publisher && <span className="text-gray-500"> ({i.publisher})</span>}
                          </td>
                          <td className="px-4 py-3 text-gray-400 font-mono">{i.issue_number}</td>
                          <td className="px-4 py-3 text-gray-300">
                            #{i.suggested_issue_number} <span className="text-gray-500">(Legacy #{i.suggested_legacy_number})</span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => fixLegacyIssue(i.comic_id)}
                              disabled={fixingLegacyId === i.comic_id}
                              title="Fix"
                              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-300 rounded-lg transition disabled:opacity-40"
                            >
                              {fixingLegacyId === i.comic_id ? 'Fixing…' : 'Fix'}
                            </button>
                            {legacyFixErrors[i.comic_id] && (
                              <p className="text-xs text-red-400 mt-1">{legacyFixErrors[i.comic_id]}</p>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'comicvine' && (
          <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4 sm:p-6 space-y-4">
            <div>
              <p className="text-sm text-gray-300 mb-1">Pull cover images from ComicVine</p>
              <p className="text-xs text-gray-500 mb-3">
                One series name per line. Each name is matched to ComicVine's top search result, then every
                issue with a cover image is added to the shared catalog — filling in a missing image on a
                comic you already have, or creating a new catalog entry if no one has logged that issue yet.
                Existing images are never overwritten, and ComicVine has no UPC data so that field is left
                untouched. Runs synchronously and can take a while for series with many issues.
              </p>
              <textarea
                value={comicvineNames}
                onChange={e => setComicvineNames(e.target.value)}
                placeholder={'Amazing Spider-Man\nSaga\nThe Walking Dead'}
                rows={5}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                onClick={handleSyncComicvine}
                disabled={syncingComicvine || comicvineNames.trim().length === 0}
                className="mt-3 flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
              >
                <RefreshCw size={14} className={syncingComicvine ? 'animate-spin' : ''} />
                {syncingComicvine ? 'Syncing…' : 'Sync'}
              </button>
            </div>

            {comicvineError && <p className="text-red-400 text-sm">{comicvineError}</p>}
            {comicvineRateLimited && (
              <p className="text-amber-400 text-sm">
                Stopped early — ComicVine's hourly rate limit was reached. Re-run with the remaining series in an hour.
              </p>
            )}

            {comicvineResults.length > 0 && (
              <>
                <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-3">
                  {comicvineResults.map((r, idx) => (
                    <div key={idx} className="bg-gray-950 border border-gray-800 rounded-xl p-3.5">
                      <p className="text-gray-300 truncate">{r.query}</p>
                      {r.status === 'not_found' ? (
                        <p className="text-amber-400 text-sm mt-1">No match found on ComicVine</p>
                      ) : (
                        <>
                          <p className="text-xs text-gray-500 mt-0.5 truncate">
                            → {r.matched_series}{r.publisher && ` (${r.publisher})`}
                          </p>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs mt-2">
                            <span className="text-gray-400">{r.issues_with_image} / {r.total_issues} w/ image</span>
                            <span className="text-green-400">{r.created} created</span>
                            <span className="text-blue-400">{r.images_filled} filled</span>
                            <span className="text-gray-500">{r.skipped} skipped</span>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>

                <div className="hidden lg:block rounded-xl border border-gray-800 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                      <tr>
                        <th className="px-4 py-3 text-left">Searched</th>
                        <th className="px-4 py-3 text-left">Matched Series</th>
                        <th className="px-4 py-3 text-right">Issues w/ Image</th>
                        <th className="px-4 py-3 text-right">Created</th>
                        <th className="px-4 py-3 text-right">Filled</th>
                        <th className="px-4 py-3 text-right">Skipped</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {comicvineResults.map((r, idx) => (
                        <tr key={idx} className="hover:bg-gray-800/50 transition">
                          <td className="px-4 py-3 text-gray-300">{r.query}</td>
                          {r.status === 'not_found' ? (
                            <td className="px-4 py-3 text-amber-400" colSpan={5}>No match found on ComicVine</td>
                          ) : (
                            <>
                              <td className="px-4 py-3 text-gray-300">
                                {r.matched_series}{r.publisher && <span className="text-gray-500"> ({r.publisher})</span>}
                              </td>
                              <td className="px-4 py-3 text-right text-gray-400">{r.issues_with_image} / {r.total_issues}</td>
                              <td className="px-4 py-3 text-right text-green-400">{r.created}</td>
                              <td className="px-4 py-3 text-right text-blue-400">{r.images_filled}</td>
                              <td className="px-4 py-3 text-right text-gray-500">{r.skipped}</td>
                            </>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        </div>
      </div>

      {editingSignup && (
        <EditSignupModal
          signup={editingSignup}
          onClose={() => setEditingSignup(null)}
          onSaved={updated => setSignups(prev => prev.map(s => s.id === updated.id ? updated : s))}
        />
      )}
    </div>
  )
}
