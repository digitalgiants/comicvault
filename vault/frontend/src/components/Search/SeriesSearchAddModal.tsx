import { useState } from 'react'
import { X, Image as ImageIcon } from 'lucide-react'
import { addScannedComic } from '../../api/scan'
import { resolveImageUrl } from '../../api/client'
import FindImageByFieldsModal from './FindImageByFieldsModal'
import { EDITABLE_FIELDS, type ImageCandidate, type ScanComicFields, type UserComic } from '../../types'

interface Props {
  initial: ScanComicFields
  onClose: () => void
  onAdded: (uc: UserComic) => void
}

const COMIC_FIELDS: { key: keyof ScanComicFields; label: string; type: string }[] = [
  { key: 'series', label: 'Series', type: 'text' },
  { key: 'publisher', label: 'Publisher', type: 'text' },
  { key: 'volume', label: 'Volume', type: 'text' },
  { key: 'issue_number', label: 'Issue Number', type: 'text' },
  { key: 'legacy_number', label: 'Lgcy Number', type: 'text' },
  { key: 'cover_date', label: 'Cover Date', type: 'date' },
  { key: 'store_date', label: 'Store Date', type: 'date' },
  { key: 'variant', label: 'Variant', type: 'text' },
  { key: 'cover_letter', label: 'Cover Letter', type: 'text' },
  { key: 'print_run', label: 'Print Run', type: 'text' },
  { key: 'writer', label: 'Writer', type: 'text' },
  { key: 'penciller', label: 'Penciller', type: 'text' },
  { key: 'inker', label: 'Inker', type: 'text' },
  { key: 'cover_artist', label: 'Cover Artist', type: 'text' },
  { key: 'average_price', label: 'Average Price ($)', type: 'number' },
]

export default function SeriesSearchAddModal({ initial, onClose, onAdded }: Props) {
  const [comicForm, setComicForm] = useState<Record<string, unknown>>(
    Object.fromEntries(COMIC_FIELDS.map(({ key }) => [key, initial[key] ?? ''])),
  )
  const [userForm, setUserForm] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(
      EDITABLE_FIELDS.map(({ key }) => [key, key === 'count' ? 1 : key === 'reserve_count' ? 0 : key === 'signed' || key === 'remarked' || key === 'do_not_sell' ? false : '']),
    ),
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [img, setImg] = useState<string | null>(initial.img ?? null)
  const [pickingImage, setPickingImage] = useState(false)

  const handleComicChange = (key: string, value: unknown) => setComicForm((prev) => ({ ...prev, [key]: value }))
  const handleUserChange = (key: string, value: unknown) => setUserForm((prev) => ({ ...prev, [key]: value }))

  async function handleSave() {
    if (!String(comicForm.series ?? '').trim()) {
      setError('Series is required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const comic: ScanComicFields = {
        ...initial,
        ...Object.fromEntries(
          COMIC_FIELDS.map(({ key, type }) => {
            const val = comicForm[key]
            if (type === 'number') return [key, val === '' ? null : Number(val)]
            return [key, val === '' ? null : val]
          }),
        ),
        img,
      }

      const uc = await addScannedComic({
        comic,
        user_comic: {
          count: userForm.count === '' ? null : Number(userForm.count),
          paid_price: userForm.paid_price === '' ? null : Number(userForm.paid_price),
          asking_price: userForm.asking_price === '' ? null : Number(userForm.asking_price),
          point_of_purchase: (userForm.point_of_purchase as string) || null,
          buy_date: (userForm.buy_date as string) || null,
          signed: Boolean(userForm.signed),
          remarked: Boolean(userForm.remarked),
          condition: (userForm.condition as string) || null,
          notes: (userForm.notes as string) || null,
        },
      })
      onAdded(uc)
      onClose()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Failed to add. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            {img ? (
              <img src={resolveImageUrl(img) ?? undefined} alt="" className="w-10 h-14 object-cover rounded" />
            ) : (
              <div className="w-10 h-14 rounded bg-gray-800 flex items-center justify-center flex-shrink-0">
                <ImageIcon size={16} className="text-gray-600" />
              </div>
            )}
            <div>
              <h2 className="font-semibold text-lg">Add to Collection</h2>
              <button
                type="button"
                onClick={() => setPickingImage(true)}
                className="flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 transition"
              >
                <ImageIcon size={12} /> {img ? 'Change cover image' : 'Find cover image'}
              </button>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">Comic Details</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {COMIC_FIELDS.map(({ key, label, type }) => (
              <div key={key}>
                <label className="block text-sm text-gray-400 mb-1">{label}</label>
                <input
                  type={type}
                  value={String(comicForm[key] ?? '')}
                  onChange={(e) => handleComicChange(key, e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            ))}
          </div>

          <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">Your Details</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {EDITABLE_FIELDS.map(({ key, label, type }) => (
              <div key={key} className={type === 'textarea' ? 'sm:col-span-2' : ''}>
                <label className="block text-sm text-gray-400 mb-1">{label}</label>
                {type === 'checkbox' ? (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={Boolean(userForm[key])}
                      onChange={(e) => handleUserChange(key, e.target.checked)}
                      className="w-4 h-4 rounded accent-brand-500"
                    />
                    <span className="text-sm text-gray-300">{userForm[key] ? 'Yes' : 'No'}</span>
                  </label>
                ) : type === 'textarea' ? (
                  <textarea
                    value={String(userForm[key] ?? '')}
                    onChange={(e) => handleUserChange(key, e.target.value)}
                    rows={3}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  />
                ) : (
                  <input
                    type={type}
                    value={String(userForm[key] ?? '')}
                    onChange={(e) => handleUserChange(key, e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                )}
              </div>
            ))}
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
            {saving ? 'Adding…' : 'Add to Collection'}
          </button>
        </div>
      </div>

      {pickingImage && (
        <FindImageByFieldsModal
          series={String(comicForm.series ?? '')}
          issueNumber={String(comicForm.issue_number ?? '')}
          publisher={String(comicForm.publisher ?? '')}
          onPick={(candidate: ImageCandidate) => { setImg(candidate.image); setPickingImage(false) }}
          onClose={() => setPickingImage(false)}
        />
      )}
    </div>
  )
}
