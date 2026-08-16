import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { backfillImage } from '../../api/search'
import type { UserComic } from '../../types'

interface Props {
  selected: UserComic[]
  onClose: () => void
}

export default function BulkFindImagesModal({ selected, onClose }: Props) {
  const [processed, setProcessed] = useState(0)
  const [found, setFound] = useState(0)
  const [alreadyHad, setAlreadyHad] = useState(0)
  const [notFound, setNotFound] = useState(0)
  const [done, setDone] = useState(false)

  // One comic can be covered by multiple selected rows (e.g. duplicate CSV
  // rows for the same catalog entry) - dedupe so it's only ever searched once.
  const comicIds = [...new Set(selected.map(uc => uc.comic.id))]

  useEffect(() => {
    let cancelledInEffect = false
    const run = async () => {
      for (const comicId of comicIds) {
        if (cancelledInEffect) return
        try {
          const result = await backfillImage(comicId)
          if (result.status === 'found') setFound(f => f + 1)
          else if (result.status === 'already_has_image') setAlreadyHad(a => a + 1)
          else setNotFound(n => n + 1)
        } catch {
          setNotFound(n => n + 1)
        }
        setProcessed(p => p + 1)
      }
      setDone(true)
    }
    run()
    return () => { cancelledInEffect = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="font-semibold text-lg">Find Images</h2>
          {done && (
            <button onClick={onClose} className="text-gray-400 hover:text-white transition">
              <X size={20} />
            </button>
          )}
        </div>

        <div className="px-6 py-5 space-y-4">
          <div>
            <div className="flex justify-between text-sm text-gray-400 mb-1.5">
              <span>{done ? 'Done' : 'Searching Metron & ComicVine…'}</span>
              <span>{processed} / {comicIds.length}</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2">
              <div
                className="bg-brand-500 h-2 rounded-full transition-all"
                style={{ width: `${comicIds.length ? (processed / comicIds.length) * 100 : 100}%` }}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center text-sm">
            <div className="bg-gray-800 rounded-lg py-2">
              <p className="text-green-400 font-semibold text-lg">{found}</p>
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
