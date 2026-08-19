import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { backfillImage, rejectCoverImage } from '../../api/search'
import { resolveImageUrl } from '../../api/client'
import type { UserComic } from '../../types'

interface Props {
  selected: UserComic[]
  onClose: () => void
}

interface ComicResult {
  comicId: number
  status: 'found' | 'already_has_image' | 'not_found'
  image: string | null
  rejected: boolean
}

export default function BulkFindImagesModal({ selected, onClose }: Props) {
  const [processed, setProcessed] = useState(0)
  const [results, setResults] = useState<ComicResult[]>([])
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  // One comic can be covered by multiple selected rows (e.g. duplicate CSV
  // rows for the same catalog entry) - dedupe so it's only ever searched once.
  const comicIds = [...new Set(selected.map(uc => uc.comic.id))]
  const comicById = new Map(selected.map(uc => [uc.comic.id, uc.comic]))

  useEffect(() => {
    let cancelledInEffect = false
    const run = async () => {
      for (const comicId of comicIds) {
        if (cancelledInEffect) return
        let status: ComicResult['status'] = 'not_found'
        let image: string | null = null
        try {
          const r = await backfillImage(comicId)
          status = r.status
          image = r.image
        } catch {
          // treated as not_found below
        }
        // Re-check after the await, not just at the top of the loop - without
        // this, an in-flight request from a cleaned-up effect instance (e.g.
        // React StrictMode's dev-only double-invoke) still lands its state
        // updates after resolving, double-counting `processed` past
        // comicIds.length and blowing the progress bar's width past 100%.
        if (cancelledInEffect) return
        setResults(prev => [...prev, { comicId, status, image, rejected: false }])
        setProcessed(p => p + 1)
      }
      if (!cancelledInEffect) setDone(true)
    }
    run()
    return () => { cancelledInEffect = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const reject = async (result: ComicResult) => {
    if (!result.image) return
    setResults(prev => prev.map(r => r.comicId === result.comicId ? { ...r, rejected: true } : r))
    try {
      await rejectCoverImage(result.comicId, result.image)
    } catch {
      setError('Failed to reject an image - it may still show up in future searches.')
    }
  }

  const found = results.filter(r => r.status === 'found')
  const alreadyHad = results.filter(r => r.status === 'already_has_image').length
  const notFound = results.filter(r => r.status === 'not_found').length

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="font-semibold text-lg">Find Images</h2>
          {done && (
            <button onClick={onClose} className="text-gray-400 hover:text-white transition">
              <X size={20} />
            </button>
          )}
        </div>

        <div className="overflow-y-auto px-6 py-5 flex-1 space-y-4">
          <div>
            <div className="flex justify-between text-sm text-gray-400 mb-1.5">
              <span>{done ? 'Done' : 'Searching Metron & ComicVine…'}</span>
              <span>{processed} / {comicIds.length}</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-brand-500 h-2 rounded-full transition-all"
                style={{ width: `${Math.min(100, comicIds.length ? (processed / comicIds.length) * 100 : 100)}%` }}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center text-sm">
            <div className="bg-gray-800 rounded-lg py-2">
              <p className="text-green-400 font-semibold text-lg">{found.length}</p>
              <p className="text-gray-500 text-xs mt-0.5">Found</p>
            </div>
            <div className="bg-gray-800 rounded-lg py-2">
              <p className="text-gray-300 font-semibold text-lg">{alreadyHad}</p>
              <p className="text-gray-500 text-xs mt-0.5">Already had one</p>
            </div>
            <div className="bg-gray-800 rounded-lg py-2">
              <p className="text-gray-300 font-semibold text-lg">{notFound}</p>
              <p className="text-gray-500 text-xs mt-0.5">Not found</p>
            </div>
          </div>

          {found.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                Review found covers — reject any that are wrong
              </p>
              <div className="space-y-1.5">
                {found.map((result) => {
                  const comic = comicById.get(result.comicId)
                  return (
                    <div key={result.comicId} className="flex items-center gap-3 bg-gray-800 rounded-lg px-3 py-2">
                      {result.image && (
                        <img
                          src={resolveImageUrl(result.image) ?? undefined}
                          alt=""
                          className="w-8 h-11 object-cover rounded border border-gray-700 flex-shrink-0"
                        />
                      )}
                      <p className="flex-1 min-w-0 text-sm text-gray-300 truncate">
                        {comic?.series}{comic?.issue_number ? ` #${comic.issue_number}` : ''}
                      </p>
                      {result.rejected ? (
                        <span className="text-xs text-gray-500 flex-shrink-0">Rejected</span>
                      ) : (
                        <button
                          onClick={() => reject(result)}
                          className="text-xs text-red-400 hover:text-red-300 flex-shrink-0 transition"
                        >
                          Reject
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {error && <p className="text-red-400 text-xs">{error}</p>}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
          {done ? (
            <button
              onClick={onClose}
              className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
            >
              Close
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-400 hover:text-white transition"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
