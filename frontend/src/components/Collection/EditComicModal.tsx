import { useEffect, useState } from 'react'
import { X, Trash2 } from 'lucide-react'
import { updateUserComic, deleteSale } from '../../api/collection'
import { availableCopies, type Sale, type UserComic, EDITABLE_FIELDS } from '../../types'

interface Props {
  item: UserComic
  onClose: () => void
  onSaved: (updated: UserComic) => void
  onItemChange?: (updated: UserComic) => void
}

export default function EditComicModal({ item, onClose, onSaved, onItemChange }: Props) {
  const [form, setForm] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [localSales, setLocalSales] = useState<Sale[]>(item.sales ?? [])

  useEffect(() => {
    const initial: Record<string, unknown> = {}
    EDITABLE_FIELDS.forEach(({ key }) => {
      const val = item[key]
      if (key === 'buy_date') {
        initial[key] = val ? (val as string).split('T')[0] : ''
      } else {
        initial[key] = val ?? (key === 'signed' || key === 'remarked' ? false : '')
      }
    })
    setForm(initial)
    setLocalSales(item.sales ?? [])
  }, [item])

  const handleChange = (key: string, value: unknown) => {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const payload: Record<string, unknown> = {}
      EDITABLE_FIELDS.forEach(({ key, type }) => {
        const val = form[key]
        if (type === 'number') payload[key] = val === '' ? null : Number(val)
        else if (type === 'checkbox') payload[key] = Boolean(val)
        else if (type === 'date') payload[key] = val === '' ? null : val
        else payload[key] = val === '' ? null : val
      })
      const updated = await updateUserComic(item.id, payload)
      onSaved({ ...updated, sales: localSales })
    } catch {
      setError('Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteSale = async (sale: Sale) => {
    if (!confirm('Remove this sale record?')) return
    await deleteSale(item.id, sale.id)
    const updated = localSales.filter(s => s.id !== sale.id)
    setLocalSales(updated)
    onItemChange?.({ ...item, sales: updated })
  }

  const avail = availableCopies({ ...item, sales: localSales })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="font-semibold text-lg">{item.comic.name}</h2>
            <p className="text-gray-400 text-sm">
              {[item.comic.publisher, item.comic.volume && `Vol. ${item.comic.volume}`, item.comic.number && `#${item.comic.number}`]
                .filter(Boolean).join(' · ')}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-4 border-b border-gray-800 bg-gray-800/40">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Comic Info (read-only)</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
            {[
              ['Writer', item.comic.writer],
              ['Artist', item.comic.artist],
              ['Pencils', item.comic.pencils],
              ['Inker', item.comic.inker],
              ['Cover Artist', item.comic.cover_artist],
              ['Variant', item.comic.variant],
              ['Print', item.comic.print],
              ['UPC', item.comic.upc],
              ['Avg Price', item.comic.average_price != null ? `$${item.comic.average_price.toFixed(2)}` : null],
            ].filter(([, v]) => v).map(([label, val]) => (
              <div key={label as string}>
                <span className="text-gray-500">{label}: </span>
                <span className="text-gray-300">{val as string}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">Your Details</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {EDITABLE_FIELDS.map(({ key, label, type }) => (
              <div key={key} className={type === 'textarea' ? 'sm:col-span-2' : ''}>
                <label className="block text-sm text-gray-400 mb-1">{label}</label>
                {type === 'checkbox' ? (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={Boolean(form[key])}
                      onChange={e => handleChange(key, e.target.checked)}
                      className="w-4 h-4 rounded accent-brand-500"
                    />
                    <span className="text-sm text-gray-300">{form[key] ? 'Yes' : 'No'}</span>
                  </label>
                ) : type === 'textarea' ? (
                  <textarea
                    value={String(form[key] ?? '')}
                    onChange={e => handleChange(key, e.target.value)}
                    rows={3}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  />
                ) : (
                  <input
                    type={type}
                    value={String(form[key] ?? '')}
                    onChange={e => handleChange(key, e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                )}
              </div>
            ))}
          </div>

          {/* Sales History */}
          <div className="mt-6 pt-4 border-t border-gray-800">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-gray-500 uppercase tracking-wider">Sales History</p>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                {avail}/{item.number_of_books ?? 1} available
              </span>
            </div>
            {localSales.length === 0 ? (
              <p className="text-sm text-gray-600 italic">No sales recorded yet.</p>
            ) : (
              <div className="space-y-2">
                {localSales.map(sale => (
                  <div key={sale.id} className="flex items-center justify-between bg-gray-800 rounded-lg px-3 py-2 text-sm">
                    <div className="flex items-center gap-4">
                      <span className="text-gray-300">{new Date(sale.sell_date).toLocaleDateString()}</span>
                      {sale.sell_price != null && (
                        <span className="text-green-400">${sale.sell_price.toFixed(2)}</span>
                      )}
                      {sale.notes && (
                        <span className="text-gray-500 italic truncate max-w-32">{sale.notes}</span>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteSale(sale)}
                      className="p-1 text-gray-600 hover:text-red-400 transition"
                      title="Delete sale"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
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
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
