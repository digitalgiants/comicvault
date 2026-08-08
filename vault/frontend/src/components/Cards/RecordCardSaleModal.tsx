import { useState } from 'react'
import { X } from 'lucide-react'
import { availableCardCopies, type UserTradingCard } from '../../types'

interface Props {
  item: UserTradingCard
  onClose: () => void
  onSaved: (ucId: number, transaction_date: string, price?: number | null, notes?: string | null) => Promise<void>
}

function todayString() {
  return new Date().toISOString().split('T')[0]
}

export default function RecordCardSaleModal({ item, onClose, onSaved }: Props) {
  const [saleDate, setSaleDate] = useState(todayString())
  const [price, setPrice] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const avail = availableCardCopies(item)

  const handleSave = async () => {
    if (!saleDate) { setError('Sale date is required.'); return }
    setSaving(true)
    setError('')
    try {
      await onSaved(
        item.id,
        saleDate,
        price !== '' ? Number(price) : null,
        notes || null,
      )
    } catch {
      setError('Failed to record sale. Please try again.')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="font-semibold text-lg">Record Sale</h2>
            <p className="text-gray-400 text-sm">{item.card.name} · {avail} of {item.count ?? 1} available</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-5 flex flex-col gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Sale Date *</label>
            <input
              type="date"
              value={saleDate}
              onChange={e => setSaleDate(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Sale Price ($)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={e => setPrice(e.target.value)}
              placeholder="Optional"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              placeholder="Optional"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-green-700 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Record Sale'}
          </button>
        </div>
      </div>
    </div>
  )
}
