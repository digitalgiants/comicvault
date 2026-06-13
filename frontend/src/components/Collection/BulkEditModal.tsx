import { useState } from 'react'
import { X } from 'lucide-react'
import { bulkUpdateUserComics } from '../../api/collection'
import type { UserComic } from '../../types'
import { EDITABLE_FIELDS } from '../../types'

interface Props {
  selected: UserComic[]
  onClose: () => void
  onSaved: () => void
}

export default function BulkEditModal({ selected, onClose, onSaved }: Props) {
  const [form, setForm] = useState<Record<string, unknown>>({})
  const [enabled, setEnabled] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const toggle = (key: string) => {
    setEnabled(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleChange = (key: string, value: unknown) => {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const activeFields = Object.entries(enabled).filter(([, v]) => v).map(([k]) => k)
      if (!activeFields.length) { onClose(); return }

      const update: Record<string, unknown> = {}
      activeFields.forEach(key => {
        const field = EDITABLE_FIELDS.find(f => f.key === key)
        const val = form[key]
        if (!field) return
        if (field.type === 'number') update[key] = val === '' || val === undefined ? null : Number(val)
        else if (field.type === 'checkbox') update[key] = Boolean(val)
        else if (field.type === 'date') update[key] = val === '' ? null : val
        else update[key] = val === '' ? null : val
      })

      await bulkUpdateUserComics(selected.map(uc => ({ id: uc.id, update })))
      onSaved()
    } catch {
      setError('Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="font-semibold text-lg">Bulk Edit</h2>
            <p className="text-gray-400 text-sm">{selected.length} comics selected — only checked fields will update</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1 space-y-3">
          {EDITABLE_FIELDS.map(({ key, label, type }) => (
            <div key={key} className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={Boolean(enabled[key])}
                onChange={() => toggle(key)}
                className="mt-1 w-4 h-4 rounded accent-brand-500 flex-shrink-0"
              />
              <div className="flex-1">
                <label className="block text-sm text-gray-300 mb-1">{label}</label>
                {enabled[key] && (
                  type === 'checkbox' ? (
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(form[key])}
                        onChange={e => handleChange(key, e.target.checked)}
                        className="w-4 h-4 rounded accent-brand-500"
                      />
                      <span className="text-sm text-gray-400">{form[key] ? 'Yes' : 'No'}</span>
                    </label>
                  ) : type === 'textarea' ? (
                    <textarea
                      value={String(form[key] ?? '')}
                      onChange={e => handleChange(key, e.target.value)}
                      rows={2}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                    />
                  ) : (
                    <input
                      type={type}
                      value={String(form[key] ?? '')}
                      onChange={e => handleChange(key, e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  )
                )}
              </div>
            </div>
          ))}
        </div>

        {error && <p className="px-6 text-red-400 text-sm">{error}</p>}

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
          >
            {saving ? 'Saving…' : `Update ${selected.length} Comics`}
          </button>
        </div>
      </div>
    </div>
  )
}
