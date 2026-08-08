import { useRef, useState } from 'react'
import { X, Camera, Image as ImageIcon } from 'lucide-react'
import { identifyCardScan, confirmCardScan } from '../../api/cards'
import type { IdentifyScanResponse, ScanCandidate, UserTradingCard } from '../../types'

interface Props {
  onClose: () => void
  onAdded: (uc: UserTradingCard) => void
  onManualFallback: () => void
}

// Resize only - no cropping, unlike PhotoCapture's fixed cover crop. The
// identification model wants the whole card in frame; this just bounds
// upload size/latency.
const MAX_DIMENSION = 1600
const JPEG_QUALITY = 0.85

async function downscaleImage(file: File): Promise<Blob> {
  const objectUrl = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve(image)
      image.onerror = reject
      image.src = objectUrl
    })
    const scale = Math.min(1, MAX_DIMENSION / Math.max(img.width, img.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(img.width * scale)
    canvas.height = Math.round(img.height * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas not supported')
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(blob => (blob ? resolve(blob) : reject(new Error('Export failed'))), 'image/jpeg', JPEG_QUALITY)
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

export default function CardScanModal({ onClose, onAdded, onManualFallback }: Props) {
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const libraryInputRef = useRef<HTMLInputElement>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [identifying, setIdentifying] = useState(false)
  const [result, setResult] = useState<IdentifyScanResponse | null>(null)
  const [selected, setSelected] = useState<ScanCandidate | null>(null)
  const [count, setCount] = useState('1')
  const [condition, setCondition] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setError('')
    setResult(null)
    setSelected(null)
    setIdentifying(true)
    setPreviewUrl(URL.createObjectURL(file))
    try {
      const blob = await downscaleImage(file)
      const res = await identifyCardScan(blob)
      setResult(res)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Failed to identify card - the identification service may be unavailable. Please try again.')
    } finally {
      setIdentifying(false)
    }
  }

  async function handleConfirm() {
    if (!result || !selected) return
    setSaving(true)
    setError('')
    try {
      const uc = await confirmCardScan(
        result.scan_id, selected.card.id,
        { count: count ? Number(count) : 1, condition: condition || undefined },
        selected.variant_id,
      )
      onAdded(uc)
    } catch {
      setError('Failed to add card. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="font-semibold text-lg">Scan Card</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleFileChange} className="hidden" />
        <input ref={libraryInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />

        <div className="overflow-y-auto px-6 py-4 flex-1">
          {!previewUrl ? (
            <div className="flex flex-col items-center gap-4 py-12">
              <p className="text-gray-400 text-sm text-center max-w-sm">
                Photograph the whole card — no need to crop, the identification model reads it as-is.
              </p>
              <div className="flex gap-2">
                <button onClick={() => cameraInputRef.current?.click()} className="flex items-center gap-1.5 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 rounded-lg transition">
                  <Camera size={16} /> Take Photo
                </button>
                <button onClick={() => libraryInputRef.current?.click()} className="flex items-center gap-1.5 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 rounded-lg transition">
                  <ImageIcon size={16} /> Choose Photo
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <img src={previewUrl} alt="" className="w-full max-h-64 object-contain rounded-lg border border-gray-700" />

              {identifying ? (
                <div className="text-center py-6">
                  <p className="text-gray-300">Identifying card…</p>
                  <p className="text-gray-500 text-sm mt-1">This can take up to a minute or two, especially on the first scan.</p>
                </div>
              ) : result && !selected ? (
                result.candidates.length === 0 ? (
                  <div className="text-center py-6">
                    <p className="text-gray-300">No confident matches found.</p>
                    {(result.detected_name || result.detected_number) && (
                      <p className="text-gray-500 text-sm mt-1">
                        Detected: {[result.detected_name, result.detected_number].filter(Boolean).join(' · ')}
                      </p>
                    )}
                    <button onClick={onManualFallback} className="mt-3 text-brand-400 hover:text-brand-300 text-sm underline">
                      Search the catalog manually instead
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500 uppercase tracking-wider">Candidates</p>
                    {result.candidates.map((c, i) => (
                      <button
                        key={i}
                        onClick={() => setSelected(c)}
                        className="w-full flex items-center gap-3 bg-gray-800 hover:bg-gray-700 rounded-lg px-3 py-2 text-left transition"
                      >
                        {c.card.image_small && (
                          <img src={c.card.image_small} alt="" className="w-8 h-11 object-cover rounded border border-gray-700 flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white truncate">{c.card.name}</p>
                          <p className="text-xs text-gray-400 truncate">
                            {[c.card.set_name, c.card.card_number && `#${c.card.card_number}`].filter(Boolean).join(' · ')}
                          </p>
                        </div>
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 flex-shrink-0">
                          {Math.round(c.confidence * 100)}%
                        </span>
                      </button>
                    ))}
                    <button onClick={onManualFallback} className="w-full text-center text-brand-400 hover:text-brand-300 text-sm underline pt-2">
                      None of these — search manually
                    </button>
                  </div>
                )
              ) : selected ? (
                <>
                  <div className="flex items-center gap-3 bg-gray-800/60 rounded-lg px-3 py-2">
                    {selected.card.image_small && (
                      <img src={selected.card.image_small} alt="" className="w-10 h-14 object-cover rounded border border-gray-700" />
                    )}
                    <div className="flex-1">
                      <p className="font-medium">{selected.card.name}</p>
                      <p className="text-xs text-gray-400">
                        {[selected.card.set_name, selected.card.card_number && `#${selected.card.card_number}`].filter(Boolean).join(' · ')}
                      </p>
                    </div>
                    <button onClick={() => setSelected(null)} className="text-sm text-gray-400 hover:text-white transition">
                      Change
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Count</label>
                      <input type="number" min="1" value={count} onChange={e => setCount(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Condition</label>
                      <input value={condition} onChange={e => setCondition(e.target.value)} placeholder="e.g. Near Mint" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          )}

          {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition">
            Cancel
          </button>
          {selected && (
            <button
              onClick={handleConfirm}
              disabled={saving}
              className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
            >
              {saving ? 'Adding…' : 'Add to Collection'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
