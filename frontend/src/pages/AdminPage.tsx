import { useEffect, useState } from 'react'
import { Shield, Trash2, UserCog } from 'lucide-react'
import api from '../api/client'

interface User {
  id: number
  email: string
  is_admin: boolean
  created_at: string
}

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)

  const fetchUsers = async () => {
    const { data } = await api.get<User[]>('/admin/users')
    setUsers(data)
    setLoading(false)
  }

  useEffect(() => { fetchUsers() }, [])

  const toggleAdmin = async (user: User) => {
    await api.patch(`/admin/users/${user.id}`, { is_admin: !user.is_admin })
    setUsers((prev) =>
      prev.map((u) => (u.id === user.id ? { ...u, is_admin: !user.is_admin } : u))
    )
  }

  const deleteUser = async (user: User) => {
    if (!confirm(`Delete user ${user.email}? This cannot be undone.`)) return
    await api.delete(`/admin/users/${user.id}`)
    setUsers((prev) => prev.filter((u) => u.id !== user.id))
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center gap-2 mb-6">
        <Shield size={24} className="text-yellow-400" />
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
      </div>

      <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-800 flex justify-between items-center">
          <h2 className="font-semibold">Users ({users.length})</h2>
        </div>

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
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-800/50 transition">
                  <td className="px-6 py-4">{user.email}</td>
                  <td className="px-6 py-4">
                    <span
                      className={`text-xs font-medium px-2 py-1 rounded-full ${
                        user.is_admin
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-gray-700 text-gray-400'
                      }`}
                    >
                      {user.is_admin ? 'Admin' : 'User'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-400">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
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
                        onClick={() => deleteUser(user)}
                        title="Delete user"
                        className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-gray-700 transition"
                      >
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
    </div>
  )
}
