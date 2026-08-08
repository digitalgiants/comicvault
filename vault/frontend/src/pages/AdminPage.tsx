import { useEffect, useState } from 'react'
import { Shield, Trash2, UserCog, CheckCircle, Monitor, RefreshCw } from 'lucide-react'
import axios from 'axios'
import api from '../api/client'
import { getBugReports, resolveBugReport } from '../api/collection'
import { getCardGames } from '../api/cards'
import type { BugReport, CardGame } from '../types'
import BugReportButton from '../components/BugReportButton'

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
  created_at: string
}

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [reports, setReports] = useState<BugReport[]>([])
  const [showResolved, setShowResolved] = useState(false)
  const [tab, setTab] = useState<'users' | 'bugs' | 'cards'>('users')
  const [loading, setLoading] = useState(true)

  const [cardGames, setCardGames] = useState<CardGame[]>([])
  const [selectedGameSlug, setSelectedGameSlug] = useState('')
  const [syncingGames, setSyncingGames] = useState(false)
  const [syncingSets, setSyncingSets] = useState(false)
  const [syncingProducts, setSyncingProducts] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)
  const [syncError, setSyncError] = useState('')

  useEffect(() => {
    api.get<AdminUser[]>('/admin/users').then(r => { setUsers(r.data); setLoading(false) })
  }, [])

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

  const toggleAdmin = async (user: AdminUser) => {
    await api.patch(`/admin/users/${user.id}`, { is_admin: !user.is_admin })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_admin: !u.is_admin } : u))
  }

  const toggleKiosk = async (user: AdminUser) => {
    await api.patch(`/admin/users/${user.id}`, { is_kiosk: !user.is_kiosk })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_kiosk: !u.is_kiosk } : u))
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

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Shield size={24} className="text-yellow-400" />
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
      </div>

      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-xl p-1 w-fit">
        {(['users', 'bugs', 'cards'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition ${tab === t ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}
          >
            {t === 'users' ? `Users (${users.length})` : t === 'bugs' ? `Bug Reports${unresolvedCount ? ` (${unresolvedCount})` : ''}` : 'Cards Sync'}
          </button>
        ))}
      </div>

      {tab === 'users' && (
        <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
          {loading ? (
            <div className="text-center text-gray-400 py-12">Loading…</div>
          ) : (
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
                        <span className={`text-xs font-medium px-2 py-1 rounded-full ${role.cls}`}>
                          {role.label}
                        </span>
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

      <BugReportButton />
    </div>
  )
}
