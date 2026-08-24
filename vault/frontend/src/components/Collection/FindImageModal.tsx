import { useEffect, useState } from 'react'
import { X, BookOpen } from 'lucide-react'
import { getImageCandidates, rejectCoverImage } from '../../api/search'
import { updateComicMetadata } from '../../api/collection'
import ImageCandidateGrid from './ImageCandidateGrid'
import type { Comic, ImageCandidate } from '../../types'

interface Props {
  comicId: number
  series: string
  issueNumber: string | null
  onClose: () => void
  onSaved: (comic: Comic) => void
}

export default function FindImageModal({ comicId, series, issueNumber, onClose, onSaved }: Props) {
  const [loading, setLoading] = useState(true)
  const [candidates, setCandidates] = useState<ImageCandidate[]>([])
  const [applying, setApplying] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getImageCandidates({ comicId })
      .then(setCandidates)
      .catch(() => setError('Failed to search for images. Please try again.'))
      .finally(() => setLoading(false))
  }, [comicId])

  const pick = async (candidate: ImageCandidate) => {
    setApplying(candidate.image)
    setError('')
    try {
      const updated = await updateComicMetadata(comicId, { img: candidate.image })
      onSaved(updated)
    } catch {
      setError('Failed to set image. Please try again.')
      setApplying(null)
    }
  }

  const reject = async (candidate: ImageCandidate) => {
    setCandidates(prev => prev.filter(c => c.image !== candidate.image))
    try {
      await rejectCoverImage(comicId, candidate.image)
    } catch {
      setError('Failed to reject image. It may still show up in future searches.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="font-semibold text-lg">Find Image</h2>
            <p className="text-gray-400 text-sm">
              {series}{issueNumber ? ` #${issueNumber}` : ''}
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
            <ImageCandidateGrid candidates={candidates} applying={applying} onPick={pick} onReject={reject} />
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
