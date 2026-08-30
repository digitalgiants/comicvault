import { useCallback, useState } from 'react'
import { CheckCircle, PlusCircle, XCircle } from 'lucide-react'
import BarcodeScanner from '../components/Scan/BarcodeScanner'
import ScanInput from '../components/Scan/ScanInput'
import BatchPanel from '../components/Scan/BatchPanel'
import ReviewAddModal from '../components/Scan/ReviewAddModal'
import { lookupBarcode, submitScanBatch } from '../api/scan'
import type { LookupAttempt, StagedItem } from '../types'

const MAX_BATCH_SIZE = 20

export default function ScanPage() {
  const [attempts, setAttempts] = useState<LookupAttempt[]>([])
  const [batchMode, setBatchMode] = useState(false)
  const [stagedItems, setStagedItems] = useState<StagedItem[]>([])
  const [batchSubmitting, setBatchSubmitting] = useState(false)
  const [batchError, setBatchError] = useState<string | null>(null)
  const [reviewing, setReviewing] = useState<Extract<LookupAttempt, { status: 'success' }> | null>(null)
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set())

  const runLookup = useCallback(async (upc12: string, ean: string | null) => {
    const id = crypto.randomUUID()
    const timestamp = new Date().toISOString()
    setAttempts((prev) => [{ id, upc12, ean, timestamp, status: 'pending' }, ...prev])

    try {
      const result = await lookupBarcode(upc12, ean)
      setAttempts((prev) =>
        prev.map((a) => {
          if (a.id !== id) return a
          return result ? { ...a, status: 'success' as const, result } : { ...a, status: 'not_found' as const }
        }),
      )
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const message = detail || (err instanceof Error ? err.message : 'Unknown error')
      setAttempts((prev) => prev.map((a) => (a.id === id ? { ...a, status: 'error' as const, message } : a)))
    }
  }, [])

  const addStagedItem = useCallback((upc12: string, ean: string | null) => {
    setStagedItems((prev) =>
      prev.length >= MAX_BATCH_SIZE ? prev : [...prev, { id: crypto.randomUUID(), upc12, ean }],
    )
  }, [])

  function handleDetected(upc12: string, ean: string | null) {
    if (batchMode) {
      addStagedItem(upc12, ean)
    } else {
      void runLookup(upc12, ean)
    }
  }

  async function submitStagedBatch() {
    if (stagedItems.length === 0) return
    setBatchSubmitting(true)
    setBatchError(null)

    const idsInOrder = stagedItems.map(() => crypto.randomUUID())
    const timestamp = new Date().toISOString()
    setAttempts((prev) => [
      ...stagedItems.map((item, i) => ({
        id: idsInOrder[i],
        upc12: item.upc12,
        ean: item.ean,
        timestamp,
        status: 'pending' as const,
      })),
      ...prev,
    ])

    const items = stagedItems.map(({ upc12, ean }) => ({ upc12, ean }))
    setStagedItems([])

    try {
      await submitScanBatch(items, (event) => {
        const id = idsInOrder[event.index]
        setAttempts((prev) =>
          prev.map((a) => {
            if (a.id !== id) return a
            if (event.status === 'success' && event.result) {
              return { ...a, status: 'success' as const, result: event.result }
            }
            if (event.status === 'not_found') {
              return { ...a, status: 'not_found' as const }
            }
            return { ...a, status: 'error' as const, message: event.message ?? 'Unknown error' }
          }),
        )
      })
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : 'Batch request failed')
    } finally {
      setBatchSubmitting(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">Scan</h1>
      <p className="text-gray-400 mb-8">
        Scan a barcode, use a hardware scanner, or type a UPC to look it up and add it to your collection.
      </p>

      <div className="space-y-4">
        <BarcodeScanner onDetected={handleDetected} />

        <div className="bg-gray-900 rounded-2xl p-5 border border-gray-800 space-y-4">
          <ScanInput onSubmit={handleDetected} />
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={batchMode}
              onChange={(e) => setBatchMode(e.target.checked)}
              className="w-4 h-4 rounded accent-brand-500"
            />
            <span className="text-sm text-gray-300">Batch mode</span>
          </label>
        </div>

        {batchMode && (
          <BatchPanel
            items={stagedItems}
            maxItems={MAX_BATCH_SIZE}
            submitting={batchSubmitting}
            error={batchError}
            onAddPasted={(codes) => codes.forEach(({ upc12, ean }) => addStagedItem(upc12, ean))}
            onRemove={(id) => setStagedItems((prev) => prev.filter((i) => i.id !== id))}
            onEdit={(id, upc12, ean) =>
              setStagedItems((prev) => prev.map((i) => (i.id === id ? { ...i, upc12, ean } : i)))
            }
            onSubmit={() => void submitStagedBatch()}
          />
        )}

        {attempts.length > 0 && (
          <div className="space-y-2">
            {attempts.map((a) => (
              <div key={a.id} className="bg-gray-900 rounded-xl px-4 py-3 border border-gray-800">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 text-xs font-mono">
                    {a.upc12}
                    {a.ean ? ` + ${a.ean}` : ''}
                  </span>
                  {a.status === 'success' && addedIds.has(a.id) && (
                    <span className="flex items-center gap-1 text-xs text-green-400">
                      <CheckCircle size={13} /> Added
                    </span>
                  )}
                </div>

                {a.status === 'pending' && <p className="text-gray-400 text-sm mt-1">Looking up…</p>}
                {a.status === 'not_found' && (
                  <p className="flex items-center gap-2 text-gray-400 text-sm mt-1">
                    <XCircle size={15} /> No issue found for that UPC
                  </p>
                )}
                {a.status === 'error' && (
                  <p className="flex items-center gap-2 text-red-400 text-sm mt-1">
                    <XCircle size={15} /> {a.message}
                  </p>
                )}
                {a.status === 'success' && (
                  <div className="flex items-center justify-between gap-3 mt-2">
                    <div className="flex items-center gap-3 min-w-0">
                      {a.result.image && (
                        <img src={a.result.image} alt="" className="w-10 h-14 object-cover rounded flex-shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className="font-medium truncate">
                          {a.result.series_name} #{a.result.issue_number}
                          {a.result.variant_name && <span className="text-gray-400"> ({a.result.variant_name})</span>}
                        </p>
                        <p className="text-gray-400 text-sm truncate">
                          {[a.result.publisher_name, a.result.series_volume ? `Vol. ${a.result.series_volume}` : null]
                            .filter(Boolean)
                            .join(' · ')}
                        </p>
                      </div>
                    </div>
                    {!addedIds.has(a.id) && (
                      <button
                        onClick={() => setReviewing(a)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition shrink-0"
                      >
                        <PlusCircle size={15} /> Add
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {reviewing && (
        <ReviewAddModal
          result={reviewing.result}
          upc12={reviewing.upc12}
          ean={reviewing.ean}
          onClose={() => setReviewing(null)}
          onAdded={() => setAddedIds((prev) => new Set(prev).add(reviewing.id))}
        />
      )}
    </div>
  )
}
