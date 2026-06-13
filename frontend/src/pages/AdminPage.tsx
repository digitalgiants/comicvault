import { useEffect, useState } from 'react'
import { Shield, Trash2, UserCog, CheckCircle } from 'lucide-react'
import api from '../api/client'
import { getBugReports, resolveBugReport } from '../api/collection'
import type { BugReport } from '../types'
import BugReportButton from '../components/BugReportButton'

interface AdminUser {
  id: number
  email: string
  is_admin: boolean
  created_at: string
}

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [reports, setReports] = useState<BugReport[]>([])
  const [showResolved, setShowResolved] = useState(false)
  const [tab, setTab] = useState<'users' | 'bugs'>('users')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<AdminUser[]>('/admin/users').then(r => { setUsers(r.data); setLoading(false) })
  }, [])

  useEffect(() => {
    getBugReports(showResolved ? undefined : false).then(setReports)
  }, [showResolved])

  const toggleAdmin = async (user: AdminUser) => {
    await api.patch(`/admin/users/${user.id}`, { is_admin: !user.is_admin })
    setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_admin: !u.is_admin } : u))
  }

  const deleteUser = async (user: AdminUser) => {
    if (!confirm(`Delete user ${user.email}? This cannot be undone.`)) return
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

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Shield size={24} className="text-yellow-400" />
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
      </div>

      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-xl p-1 w-fit">
        {(['users', 'bugs'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition ${tab === t ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}
          >
            {t === 'users' ? `Users (${users.length})` : `Bug Reports${unresolvedCount ? ` (${unresolvedCount})` : ''}`}
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
                  <th className="px-6 py-3 text-left">Email</th>
                  <th className="px-6 py-3 text-left">Role</th>
                  <th className="px-6 py-3 text-left">Joined</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {users.map(user => (
                  <tr key={user.id} className="hover:bg-gray-800/50 transition">
                    <td className="px-6 py-4">{user.email}</td>
                    <td className="px-6 py-4">
                      <span className={`text-xs font-medium px-2 py-1 rounded-full ${user.is_admin ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700 text-gray-400'}`}>
                        {user.is_admin ? 'Admin' : 'User'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-400">{new Date(user.created_at).toLocaleDateString()}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => toggleAdmin(user)} title={user.is_admin ? 'Revoke admin' : 'Make admin'} className="p-2 rounded-lg text-gray-400 hover:text-yellow-400 hover:bg-gray-700 transition">
                          <UserCog size={16} />
                        </button>
                        <button onClick={() => deleteUser(user)} title="Delete user" className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-gray-700 transition">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
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
                        <span className="text-xs font-medium text-gray-400">{r.user_email}</span>
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

      <BugReportButton />
    </div>
  )
}
