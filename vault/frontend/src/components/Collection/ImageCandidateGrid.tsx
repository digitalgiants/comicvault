import { resolveImageUrl } from '../../api/client'
import type { ImageCandidate } from '../../types'

const PROVIDER_LABEL: Record<string, string> = { metron: 'Metron', comicvine: 'ComicVine' }

interface Props {
  candidates: ImageCandidate[]
  applying: string | null
  onPick: (candidate: ImageCandidate) => void
}

export default function ImageCandidateGrid({ candidates, applying, onPick }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
      {candidates.map((candidate) => (
        <button
          key={candidate.image}
          onClick={() => onPick(candidate)}
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
  )
}
