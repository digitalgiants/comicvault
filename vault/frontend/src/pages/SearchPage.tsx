import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, BookOpen, Search as SearchIcon, X } from 'lucide-react'
import BugReportButton from '../components/BugReportButton'
import { useDebounce } from '../hooks/useDebounce'
import { getIssueFields, getSeriesIssues, searchSeries } from '../api/search'
import type { ExternalIssueSummary, ExternalSeriesResult, ScanComicFields } from '../types'
import SeriesSearchAddModal from '../components/Search/SeriesSearchAddModal'

const PROVIDER_LABEL: Record<string, string> = { metron: 'Metron', comicvine: 'ComicVine' }
const PROVIDER_BADGE: Record<string, string> = {
  metron: 'bg-blue-900/50 text-blue-300',
  comicvine: 'bg-purple-900/50 text-purple-300',
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounce(query, 400)
  const [results, setResults] = useState<ExternalSeriesResult[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [searching, setSearching] = useState(false)

  const [selectedSeries, setSelectedSeries] = useState<ExternalSeriesResult | null>(null)
  const [issues, setIssues] = useState<ExternalIssueSummary[]>([])
  const [issuesLoading, setIssuesLoading] = useState(false)

  const [fields, setFields] = useState<ScanComicFields | null>(null)
  const [detailLoading, setDetailLoading] = useState<string | null>(null)

  const requestId = useRef(0)

  useEffect(() => {
    if (debouncedQuery.trim().length < 2) {
      setResults([])
      setWarnings([])
      return
    }

    const id = ++requestId.current
    setSearching(true)
    searchSeries(debouncedQuery.trim())
      .then((data) => {
        if (id !== requestId.current) return
        setResults(data.results)
        setWarnings(data.warnings)
      })
      .catch(() => {
        if (id !== requestId.current) return
        setWarnings(['Search failed. Please try again.'])
      })
      .finally(() => {
        if (id === requestId.current) setSearching(false)
      })
  }, [debouncedQuery])

  const selectSeries = async (series: ExternalSeriesResult) => {
    setSelectedSeries(series)
    setIssues([])
    setIssuesLoading(true)
    try {
      const data = await getSeriesIssues(series.provider, series.provider_series_id)
      setIssues(data)
    } finally {
      setIssuesLoading(false)
    }
  }

  const selectIssue = async (issue: ExternalIssueSummary) => {
    setDetailLoading(issue.provider_issue_id)
    try {
      const data = await getIssueFields(issue.provider, issue.provider_issue_id)
      setFields(data)
    } finally {
      setDetailLoading(null)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">Search & Add</h1>
      <p className="text-gray-400 mb-8">
        Search Metron and ComicVine by series title, then drill down to find and add an issue —
        useful for older books where UPC lookup doesn't work.
      </p>

      {selectedSeries ? (
        <div>
          <button
            onClick={() => { setSelectedSeries(null); setIssues([]) }}
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition mb-4"
          >
            <ArrowLeft size={16} /> Back to series results
          </button>

          <div className="flex items-center gap-3 mb-6">
            {selectedSeries.image && (
              <img src={selectedSeries.image} alt="" className="w-12 h-16 object-cover rounded" />
            )}
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-lg">{selectedSeries.name}</h2>
                <span className={`text-xs px-2 py-0.5 rounded-full ${PROVIDER_BADGE[selectedSeries.provider]}`}>
                  {PROVIDER_LABEL[selectedSeries.provider]}
                </span>
              </div>
              <p className="text-gray-400 text-sm">
                {[selectedSeries.publisher, selectedSeries.start_year].filter(Boolean).join(' · ')}
              </p>
            </div>
          </div>

          {issuesLoading ? (
            <p className="text-gray-400">Loading issues…</p>
          ) : issues.length === 0 ? (
            <p className="text-gray-500 italic">No issues found for this series.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {issues.map((issue) => (
                <button
                  key={issue.provider_issue_id}
                  onClick={() => selectIssue(issue)}
                  disabled={detailLoading === issue.provider_issue_id}
                  className="flex items-center gap-3 bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl px-4 py-3 text-left transition disabled:opacity-50"
                >
                  {issue.image ? (
                    <img src={issue.image} alt="" className="w-10 h-14 object-cover rounded flex-shrink-0" />
                  ) : (
                    <BookOpen size={20} className="text-gray-600 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="font-medium truncate">
                      {issue.number ? `#${issue.number}` : 'Untitled'}
                    </p>
                    {issue.cover_date && <p className="text-xs text-gray-500">{issue.cover_date}</p>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="relative mb-6">
            <SearchIcon size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by series title…"
              className="w-full bg-gray-900 border border-gray-700 rounded-xl pl-11 pr-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {warnings.length > 0 && (
            <div className="mb-6 bg-amber-900/30 border border-amber-700/50 text-amber-300 rounded-xl px-4 py-3 flex items-start gap-2">
              <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
              <div className="text-sm space-y-0.5">
                {warnings.map((w, i) => <p key={i}>{w}</p>)}
              </div>
              <button onClick={() => setWarnings([])} className="ml-auto text-amber-400 hover:text-amber-200">
                <X size={16} />
              </button>
            </div>
          )}

          {searching ? (
            <p className="text-gray-400">Searching…</p>
          ) : debouncedQuery.trim().length >= 2 && results.length === 0 ? (
            <p className="text-gray-500 italic">No results found in either database — try a different title.</p>
          ) : (
            <div className="space-y-2">
              {results.map((series) => (
                <button
                  key={`${series.provider}-${series.provider_series_id}`}
                  onClick={() => selectSeries(series)}
                  className="w-full flex items-center gap-3 bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl px-4 py-3 text-left transition"
                >
                  {series.image ? (
                    <img src={series.image} alt="" className="w-10 h-14 object-cover rounded flex-shrink-0" />
                  ) : (
                    <BookOpen size={20} className="text-gray-600 flex-shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{series.name}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${PROVIDER_BADGE[series.provider]}`}>
                        {PROVIDER_LABEL[series.provider]}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500">
                      {[series.publisher, series.start_year, series.issue_count ? `${series.issue_count} issues` : null]
                        .filter(Boolean).join(' · ')}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      <BugReportButton />

      {fields && (
        <SeriesSearchAddModal
          initial={fields}
          onClose={() => setFields(null)}
          onAdded={() => setFields(null)}
        />
      )}
    </div>
  )
}
