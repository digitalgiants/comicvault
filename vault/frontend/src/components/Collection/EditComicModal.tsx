import { useEffect, useState } from 'react'
import axios from 'axios'
import { X, Trash2, Search } from 'lucide-react'
import { updateUserComic, updateComicMetadata, deleteSale, updateSale, uploadPersonalPhoto } from '../../api/collection'
import { findUpc } from '../../api/search'
import { resolveImageUrl } from '../../api/client'
import { availableCopies, type Sale, type UserComic, EDITABLE_FIELDS, visibleEditableFields } from '../../types'
import { useAuth } from '../../hooks/useAuth'
import PhotoCapture from './PhotoCapture'

interface Props {
  item: UserComic
  onClose: () => void
  onSaved: (updated: UserComic) => void
  onItemChange?: (updated: UserComic) => void
}

export default function EditComicModal({ item, onClose, onSaved, onItemChange }: Props) {
  const { user } = useAuth()
  const isCollector = !!user?.is_collector
  const [form, setForm] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [localSales, setLocalSales] = useState<Sale[]>(item.sales ?? [])
  const [personalImg, setPersonalImg] = useState<string | null>(item.personal_img)
  const [upcValue, setUpcValue] = useState(item.comic.upc ?? '')
  const [coverArtistValue, setCoverArtistValue] = useState(item.comic.cover_artist ?? '')
  const [coverLetterValue, setCoverLetterValue] = useState(item.comic.cover_letter ?? '')
  const [volumeValue, setVolumeValue] = useState(item.comic.volume ?? '')
  const [findingUpc, setFindingUpc] = useState(false)
  const [upcLookupMessage, setUpcLookupMessage] = useState('')

  useEffect(() => {
    const initial: Record<string, unknown> = {}
    EDITABLE_FIELDS.forEach(({ key }) => {
      const val = item[key]
      if (key === 'buy_date') {
        initial[key] = val ? (val as string).split('T')[0] : ''
      } else {
        initial[key] = val ?? (key === 'signed' || key === 'remarked' || key === 'do_not_sell' ? false : '')
      }
    })
    setForm(initial)
    setLocalSales(item.sales ?? [])
    setPersonalImg(item.personal_img)
    setUpcValue(item.comic.upc ?? '')
    setCoverArtistValue(item.comic.cover_artist ?? '')
    setCoverLetterValue(item.comic.cover_letter ?? '')
    setVolumeValue(item.comic.volume ?? '')
  }, [item])

  const handleChange = (key: string, value: unknown) => {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const handleFindUpc = async () => {
    if (!item.comic.issue_number) {
      setUpcLookupMessage('No issue number on file to search with.')
      return
    }
    setFindingUpc(true)
    setUpcLookupMessage('')
    try {
      const result = await findUpc(item.comic.series, item.comic.issue_number, item.comic.publisher)
      if (result.upc) {
        setUpcValue(result.upc)
      } else {
        setUpcLookupMessage('No UPC found on GCD for this issue.')
      }
    } catch {
      setUpcLookupMessage('UPC search failed. Please try again.')
    } finally {
      setFindingUpc(false)
    }
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

      let comic = updated.comic
      const metadataUpdates: { upc?: string | null; cover_artist?: string | null; cover_letter?: string | null; volume?: string | null } = {}
      const trimmedUpc = upcValue.trim() || null
      const trimmedCoverArtist = coverArtistValue.trim() || null
      const trimmedCoverLetter = coverLetterValue.trim() || null
      const trimmedVolume = volumeValue.trim() || null
      if (trimmedUpc !== (item.comic.upc ?? null)) metadataUpdates.upc = trimmedUpc
      if (trimmedCoverArtist !== (item.comic.cover_artist ?? null)) metadataUpdates.cover_artist = trimmedCoverArtist
      if (trimmedCoverLetter !== (item.comic.cover_letter ?? null)) metadataUpdates.cover_letter = trimmedCoverLetter
      if (trimmedVolume !== (item.comic.volume ?? null)) metadataUpdates.volume = trimmedVolume

      if (Object.keys(metadataUpdates).length > 0) {
        try {
          // A volume change (or any other identity field) may merge this
          // comic into a pre-existing catalog entry that already matches -
          // the returned comic can be a different id than item.comic.id.
          comic = await updateComicMetadata(item.comic.id, metadataUpdates)
        } catch (err) {
          const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null
          setError(detail || 'Failed to save UPC / Cover Artist / Cover Letter / Volume. Please try again.')
          setSaving(false)
          onSaved({ ...updated, sales: localSales })
          return
        }
      }

      onSaved({ ...updated, comic, sales: localSales })
    } catch {
      setError('Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const handleSalePriceCommit = async (sale: Sale, raw: string) => {
    const price = raw === '' ? null : Number(raw)
    if (price === sale.sell_price) return
    try {
      const updated = await updateSale(item.id, sale.id, price)
      const nextSales = localSales.map(s => s.id === sale.id ? updated : s)
      setLocalSales(nextSales)
      onItemChange?.({ ...item, sales: nextSales })
    } catch {
      setError('Failed to update sale price.')
    }
  }

  const handlePhotoUploaded = (updated: UserComic) => {
    setPersonalImg(updated.personal_img)
    onItemChange?.({ ...item, sales: localSales, personal_img: updated.personal_img, comic: updated.comic })
  }

  const handleRemovePhoto = async () => {
    if (!confirm('Remove this photo?')) return
    const updated = await updateUserComic(item.id, { personal_img: null })
    setPersonalImg(null)
    onItemChange?.({ ...item, sales: localSales, personal_img: null, comic: updated.comic })
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
            <h2 className="font-semibold text-lg">{item.comic.series}</h2>
            <p className="text-gray-400 text-sm">
              {[item.comic.publisher, item.comic.volume && `Vol. ${item.comic.volume}`, item.comic.issue_number && `#${item.comic.issue_number}`]
                .filter(Boolean).join(' · ')}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-4 border-b border-gray-800 bg-gray-800/40">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Comic Info (read-only)</p>
          <div className="flex gap-4">
            {(item.comic.master_photo || item.comic.img) && (
              <img
                src={resolveImageUrl(item.comic.master_photo || item.comic.img) ?? undefined}
                alt=""
                className="w-16 h-24 object-cover rounded-lg border border-gray-700 flex-shrink-0"
              />
            )}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm flex-1">
              {[
                ['Writer', item.comic.writer],
                ['Penciller', item.comic.penciller],
                ['Inker', item.comic.inker],
                ['Variant', item.comic.variant],
                ['Print Run', item.comic.print_run],
                ['Cover Date', item.comic.cover_date],
                ['Store Date', item.comic.store_date],
                ['Newstand', item.comic.newstand == null ? null : (item.comic.newstand ? 'Yes' : 'No')],
                ['Avg Price', item.comic.average_price != null ? `$${item.comic.average_price.toFixed(2)}` : null],
              ].filter(([, v]) => v).map(([label, val]) => (
                <div key={label as string}>
                  <span className="text-gray-500">{label}: </span>
                  <span className="text-gray-300">{val as string}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1">
          <div className="mb-6 pb-4 border-b border-gray-800">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Shared Catalog Fields</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">UPC</label>
                <div className="flex gap-2">
                  <input
                    value={upcValue}
                    onChange={e => { setUpcValue(e.target.value); setUpcLookupMessage('') }}
                    placeholder="e.g. 76194130546700111"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  {!upcValue && (
                    <button
                      type="button"
                      onClick={handleFindUpc}
                      disabled={findingUpc}
                      title="Search GCD for this issue's UPC"
                      className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-300 rounded-lg transition disabled:opacity-50"
                    >
                      <Search size={14} />
                      {findingUpc ? 'Searching…' : 'Find UPC'}
                    </button>
                  )}
                </div>
                {upcLookupMessage && <p className="text-xs text-gray-500 mt-1">{upcLookupMessage}</p>}
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Cover Artist</label>
                <input
                  value={coverArtistValue}
                  onChange={e => setCoverArtistValue(e.target.value)}
                  placeholder="e.g. Jim Lee"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Cover Letter</label>
                <input
                  value={coverLetterValue}
                  onChange={e => setCoverLetterValue(e.target.value)}
                  placeholder="e.g. A"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Volume</label>
                <input
                  value={volumeValue}
                  onChange={e => setVolumeValue(e.target.value)}
                  placeholder="e.g. 2"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Changing this to match another comic already in the catalog merges into it - the entry you're editing now disappears.
                </p>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Shared across the catalog — useful for variant covers that didn't match any lookup, or to distinguish covers that share the same issue number.
            </p>
          </div>

          <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">Your Details</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {visibleEditableFields(isCollector).map(({ key, label, type, options }) => (
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
                ) : type === 'select' ? (
                  <select
                    value={String(form[key] ?? '')}
                    onChange={e => handleChange(key, e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option value="">—</option>
                    {Boolean(form[key]) && !options?.includes(String(form[key])) && (
                      <option value={String(form[key])}>{String(form[key])}</option>
                    )}
                    {options?.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
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

          {/* Personal Photo */}
          <div className="mt-6 pt-4 border-t border-gray-800">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Your Photo</p>
            <div className="flex items-center gap-4">
              {personalImg ? (
                <img
                  src={resolveImageUrl(personalImg) ?? undefined}
                  alt="Your copy"
                  className="w-20 h-28 object-cover rounded-lg border border-gray-700"
                />
              ) : (
                <div className="w-20 h-28 bg-gray-800 rounded-lg flex items-center justify-center text-gray-600 text-xs text-center px-1">
                  No Photo
                </div>
              )}
              <div className="flex flex-col gap-2">
                <PhotoCapture onUpload={blob => uploadPersonalPhoto(item.id, blob)} onUploaded={handlePhotoUploaded} />
                {personalImg && (
                  <button
                    type="button"
                    onClick={handleRemovePhoto}
                    className="text-sm text-gray-500 hover:text-red-400 transition text-left"
                  >
                    Remove photo
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Sales History */}
          {!isCollector && (
            <div className="mt-6 pt-4 border-t border-gray-800">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-gray-500 uppercase tracking-wider">Sales History</p>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                  {avail}/{item.count ?? 1} available
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
                        <span className="flex items-center gap-1 text-green-400">
                          $
                          <input
                            type="number"
                            step="0.01"
                            defaultValue={sale.sell_price ?? ''}
                            onBlur={e => handleSalePriceCommit(sale, e.target.value)}
                            placeholder="0.00"
                            className="w-20 bg-gray-900 border border-gray-700 rounded px-1.5 py-0.5 text-green-400 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
                          />
                        </span>
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
          )}
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
