import { useEffect, useState } from 'react'
import { X, BookOpen } from 'lucide-react'
import { getImageCandidates } from '../../api/search'
import { updateComicMetadata } from '../../api/collection'
import { resolveImageUrl } from '../../api/client'
import type { Comic, ImageCandidate, UserComic } from '../../types'

const PROVIDER_LABEL: Record<string, string> = { metron: 'Metron', comicvine: 'ComicVine' }

interface Props {
  item: UserComic
  onClose: () => void
  onSaved: (comic: Comic) => void
}

export default function FindImageModal({ item, onClose, onSaved }: Props) {
  const [loading, setLoading] = useState(true)
  const [candidates, setCandidates] = useState<ImageCandidate[]>([])
  const [applying, setApplying] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getImageCandidates(item.comic.id)
      .then(setCandidates)
      .catch(() => setError('Failed to search for images. Please try again.'))
      .finally(() => setLoading(false))
  }, [item.comic.id])

  const pick = async (candidate: ImageCandidate) => {
    setApplying(candidate.image)
    setError('')
    try {
      const updated = await updateComicMetadata(item.comic.id, { img: candidate.image })
      onSaved(updated)
    } catch {
      setError('Failed to set image. Please try again.')
      setApplying(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="font-semibold text-lg">Find Image</h2>
            <p className="text-gray-400 text-sm">
              {item.comic.series}{item.comic.issue_number ? ` #${item.comic.issue_number}` : ''}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1">
          {loading ? (
            <p className="text-gray-400">Searching Metron and ComicVine…</p>
          ) : error ? (
            <p className="text-red-400 text-sm">{error}</p>
          ) : candidates.length === 0 ? (
            <p className="text-gray-500 italic">
              No cover images found for this issue on Metron or ComicVine.
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {candidates.map((candidate) => (
                <button
                  key={candidate.image}
                  onClick={() => pick(candidate)}
                  disabled={applying !== null}
                  className="bg-gray-800 border border-gray-700 hover:border-brand-500 rounded-xl overflow-hidden text-left transition disabled:opacity-50"
                >
                  <div className="aspect-[2/3] bg-gray-950 flex items-center justify-center">
                    {applying === candidate.image ? (
                      <p className="text-xs text-gray-400">Applying…</p>
                    ) : (
                      <img
                        src={resolveImageUrl(candidate.image) ?? undefined}
                        alt=""
                        className="w-full h-full object-cover"
                        onError={(e) => { e.currentTarget.style.display = 'none' }}
                      />
                    )}
                  </div>
                  <div className="p-2">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-900/50 text-blue-300">
                      {PROVIDER_LABEL[candidate.provider] ?? candidate.provider}
                    </span>
                    <p className="text-xs text-gray-500 mt-1 truncate">{candidate.series_name}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {!loading && candidates.length === 0 && (
          <div className="px-6 py-4 border-t border-gray-800 text-xs text-gray-500 flex items-center gap-2">
            <BookOpen size={14} className="flex-shrink-0" />
            Try searching manually from the Search & Add page instead.
          </div>
        )}
      </div>
    </div>
  )
}
