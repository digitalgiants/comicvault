import { useEffect, useState } from 'react'
import { X, BookOpen } from 'lucide-react'
import { getImageCandidates } from '../../api/search'
import ImageCandidateGrid from '../Collection/ImageCandidateGrid'
import type { ImageCandidate } from '../../types'

interface Props {
  series: string
  issueNumber: string
  publisher?: string | null
  onPick: (candidate: ImageCandidate) => void
  onClose: () => void
}

export default function FindImageByFieldsModal({ series, issueNumber, publisher, onPick, onClose }: Props) {
  const [loading, setLoading] = useState(true)
  const [candidates, setCandidates] = useState<ImageCandidate[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    getImageCandidates({ series, issueNumber, publisher })
      .then(setCandidates)
      .catch(() => setError('Failed to search for images. Please try again.'))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="font-semibold text-lg">Find Image</h2>
            <p className="text-gray-400 text-sm">{series}{issueNumber ? ` #${issueNumber}` : ''}</p>
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
            <ImageCandidateGrid candidates={candidates} applying={null} onPick={onPick} />
          )}
        </div>

        {!loading && candidates.length === 0 && (
          <div className="px-6 py-4 border-t border-gray-800 text-xs text-gray-500 flex items-center gap-2">
            <BookOpen size={14} className="flex-shrink-0" />
            You can still add the comic without a cover and use Find Image on it later.
          </div>
        )}
      </div>
    </div>
  )
}
