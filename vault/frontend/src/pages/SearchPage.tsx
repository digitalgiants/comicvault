import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, BookOpen, RotateCcw, Search as SearchIcon, X } from 'lucide-react'
import { getIssueFields, getSeriesIssues, searchSeries } from '../api/search'
import { lookupBarcode } from '../api/scan'
import { lookupResultToComicFields, type ExternalIssueSummary, type ExternalSeriesResult, type ScanComicFields } from '../types'
import SeriesSearchAddModal from '../components/Search/SeriesSearchAddModal'

const PROVIDER_LABEL: Record<string, string> = { metron: 'Metron', comicvine: 'ComicVine', gcd: 'GCD' }
const PROVIDER_BADGE: Record<string, string> = {
  metron: 'bg-blue-900/50 text-blue-300',
  comicvine: 'bg-purple-900/50 text-purple-300',
  gcd: 'bg-green-900/50 text-green-300',
}

export default function SearchPage() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [issueNumber, setIssueNumber] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const [results, setResults] = useState<ExternalSeriesResult[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [searching, setSearching] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const sentinelRef = useRef<HTMLDivElement>(null)

  const [selectedSeries, setSelectedSeries] = useState<ExternalSeriesResult | null>(null)
  const [issues, setIssues] = useState<ExternalIssueSummary[]>([])
  const [issuesLoading, setIssuesLoading] = useState(false)
  const [noIssueMatch, setNoIssueMatch] = useState(false)

  const [searchedWithNumber, setSearchedWithNumber] = useState(false)
  const [huntingForIssue, setHuntingForIssue] = useState(false)
  const [issueMatches, setIssueMatches] = useState<{ series: ExternalSeriesResult; issue: ExternalIssueSummary }[]>([])
  const [noIssueAnywhere, setNoIssueAnywhere] = useState(false)
  const [browseAllOverride, setBrowseAllOverride] = useState(false)

  const [fields, setFields] = useState<ScanComicFields | null>(null)
  const [detailLoading, setDetailLoading] = useState<string | null>(null)
  const [upcNotFound, setUpcNotFound] = useState(false)

  const requestId = useRef(0)

  // A UPC-shaped query (12 or 17 digits, an optional space/dash separator -
  // same digit-only extraction ScanInput.tsx uses) means the user is trying
  // to look up one specific book by barcode, not search by series title -
  // route it through the same UPC lookup the Scan page uses instead of a
  // fuzzy series-name search, which would never match a number against a
  // title (see the "No results found" bug this was reported as).
  const runUpcLookup = async (digits: string) => {
    const upc12 = digits.slice(0, 12)
    const ean5 = digits.length === 17 ? digits.slice(12) : null
    const id = ++requestId.current
    setSearching(true)
    setHasSearched(true)
    setSearchedWithNumber(false)
    setIssueMatches([])
    setNoIssueAnywhere(false)
    setBrowseAllOverride(false)
    setHasMore(false)
    setResults([])
    setWarnings([])
    setUpcNotFound(false)
    try {
      const result = await lookupBarcode(upc12, ean5)
      if (id !== requestId.current) return
      if (result) {
        setFields(lookupResultToComicFields(result, upc12, ean5))
      } else {
        setUpcNotFound(true)
      }
    } catch {
      if (id !== requestId.current) return
      setWarnings(['UPC lookup failed. Please try again.'])
    } finally {
      if (id === requestId.current) setSearching(false)
    }
  }

  const runSearch = (queryOverride?: string, issueOverride?: string) => {
    const trimmed = (queryOverride ?? query).trim()
    if (trimmed.length < 2) return

    const digits = trimmed.replace(/\D/g, '')
    if (digits.length === 12 || digits.length === 14 || digits.length === 17) {
      runUpcLookup(digits)
      return
    }

    const trimmedNumber = (issueOverride ?? issueNumber).trim()
    const id = ++requestId.current
    setSearching(true)
    setHasSearched(true)
    setSearchedWithNumber(!!trimmedNumber)
    setIssueMatches([])
    setNoIssueAnywhere(false)
    setBrowseAllOverride(false)
    setHasMore(false)
    setUpcNotFound(false)
    searchSeries(trimmed)
      .then(async (data) => {
        if (id !== requestId.current) return
        setResults(data.results)
        setWarnings(data.warnings)
        setHasMore(data.has_more)
        setSearching(false)

        // With an issue number given, don't make the user pick a series at
        // all - hunt for that exact issue across the matching series and
        // land directly on it.
        if (trimmedNumber && data.results.length > 0) {
          await huntForIssue(data.results, trimmedNumber)
        }
      })
      .catch(() => {
        if (id !== requestId.current) return
        setResults([])
        setWarnings(['Search failed. Please try again.'])
        setSearching(false)
      })
  }

  // Infinite scroll continuation - only ever paginates GCD (the only branch
  // that ever sets has_more; see routes/search.py), so offsetting by the
  // number of results already loaded always lines up with GCD's own list.
  const loadMore = useCallback(() => {
    if (loadingMore || !hasMore) return
    const trimmed = query.trim()
    if (trimmed.length < 2) return
    const id = requestId.current
    setLoadingMore(true)
    searchSeries(trimmed, results.length)
      .then((data) => {
        if (id !== requestId.current) return
        setResults(prev => [...prev, ...data.results])
        setHasMore(data.has_more)
      })
      .finally(() => {
        if (id === requestId.current) setLoadingMore(false)
      })
  }, [loadingMore, hasMore, query, results.length])

  useEffect(() => {
    const el = sentinelRef.current
    if (!el || !hasMore) return
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) loadMore() },
      { rootMargin: '300px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasMore, loadMore])

  // Deep-link support (e.g. from Upload's "Declined Imports" -> "Search
  // manually"): seed the boxes and run the search once on mount if the URL
  // has ?series=&issue=. Passed as explicit overrides rather than relying on
  // the query/issueNumber state set just above, since state updates aren't
  // visible within the same synchronous effect run.
  useEffect(() => {
    const seriesParam = searchParams.get('series')
    if (!seriesParam) return
    const issueParam = searchParams.get('issue') ?? ''
    setQuery(seriesParam)
    setIssueNumber(issueParam)
    runSearch(seriesParam, issueParam)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Checks the top-ranked series match first (cheap, and right most of the
  // time for a specific-enough title). Only if that comes up empty do we pay
  // the cost of checking every other candidate, and only then show a picker
  // - scoped to just the series that actually have that issue, never the
  // full series-name list.
  const huntForIssue = async (candidates: ExternalSeriesResult[], number: string) => {
    setHuntingForIssue(true)
    try {
      const [top, ...rest] = candidates
      const topHits = await getSeriesIssues(top.provider, top.provider_series_id, { number, seriesName: top.name })
      if (topHits.length === 1) {
        await openIssue(top, topHits[0])
        return
      }

      const restHits = await Promise.all(
        rest.map(async (series) => {
          const hits = await getSeriesIssues(series.provider, series.provider_series_id, { number, seriesName: series.name })
          return hits.map((issue) => ({ series, issue }))
        })
      )
      const allMatches = [
        ...topHits.map((issue) => ({ series: top, issue })),
        ...restHits.flat(),
      ]

      if (allMatches.length === 1) {
        await openIssue(allMatches[0].series, allMatches[0].issue)
        return
      }
      if (allMatches.length === 0) {
        setNoIssueAnywhere(true)
      } else {
        setIssueMatches(allMatches)
      }
    } finally {
      setHuntingForIssue(false)
    }
  }

  const openIssue = async (series: ExternalSeriesResult, issue: ExternalIssueSummary) => {
    setSelectedSeries(series)
    setIssues([issue])
    setNoIssueMatch(false)
    await selectIssue(issue)
  }

  const selectSeries = async (series: ExternalSeriesResult) => {
    setSelectedSeries(series)
    setIssues([])
    setNoIssueMatch(false)
    setIssuesLoading(true)
    try {
      const trimmedNumber = issueNumber.trim()
      const data = await getSeriesIssues(series.provider, series.provider_series_id, {
        number: trimmedNumber || undefined,
        seriesName: series.name,
      })
      setIssues(data)
      if (trimmedNumber && data.length === 1) {
        setIssuesLoading(false)
        await selectIssue(data[0])
        return
      }
      if (trimmedNumber && data.length === 0) {
        setNoIssueMatch(true)
      }
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

  const resetSearch = () => {
    requestId.current++ // invalidate any in-flight search response
    setQuery('')
    setIssueNumber('')
    setHasSearched(false)
    setResults([])
    setWarnings([])
    setSearching(false)
    setHasMore(false)
    setLoadingMore(false)
    setSelectedSeries(null)
    setIssues([])
    setIssuesLoading(false)
    setNoIssueMatch(false)
    setSearchedWithNumber(false)
    setHuntingForIssue(false)
    setIssueMatches([])
    setNoIssueAnywhere(false)
    setBrowseAllOverride(false)
    setFields(null)
    setDetailLoading(null)
    setUpcNotFound(false)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold">Search & Add</h1>
        {hasSearched && (
          <button
            onClick={resetSearch}
            className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition"
          >
            <RotateCcw size={14} /> Start over
          </button>
        )}
      </div>
      <p className="text-gray-400 mb-8">
        Search Metron and ComicVine by series title, then drill down to find and add an issue —
        useful for older books where UPC lookup doesn't work. You can also paste/type a UPC
        (12 or 17 digits) directly into the search box for a direct barcode lookup.
      </p>

      {selectedSeries ? (
        <div>
          <button
            onClick={() => { setSelectedSeries(null); setIssues([]); setNoIssueMatch(false) }}
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
            <p className="text-gray-500 italic">
              {noIssueMatch
                ? `No issue #${issueNumber.trim()} found for this series.`
                : 'No issues found for this series.'}
            </p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {issues.map((issue) => (
                <button
                  key={issue.provider_issue_id}
                  onClick={() => selectIssue(issue)}
                  disabled={detailLoading === issue.provider_issue_id}
                  className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl overflow-hidden text-left transition disabled:opacity-50"
                >
                  <div className="aspect-[2/3] bg-gray-800 flex items-center justify-center">
                    {issue.image ? (
                      <img src={issue.image} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <BookOpen size={28} className="text-gray-600" />
                    )}
                  </div>
                  <div className="p-3">
                    <p className="font-medium truncate">
                      {issue.number ? `#${issue.number}` : 'Untitled'}
                      {issue.legacy_number && <span className="text-gray-500"> (Legacy #{issue.legacy_number})</span>}
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
          <div className="flex flex-col sm:flex-row gap-2 mb-2">
            <div className="relative flex-1">
              <SearchIcon size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runSearch()}
                placeholder="Search by series title, or paste a UPC…"
                className="w-full bg-gray-900 border border-gray-700 rounded-xl pl-11 pr-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <input
              value={issueNumber}
              onChange={(e) => setIssueNumber(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
              placeholder="Issue # (optional)"
              className="w-full sm:w-40 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              onClick={() => runSearch()}
              disabled={searching || query.trim().length < 2}
              className="px-6 py-3 bg-brand-500 hover:bg-brand-600 text-white font-medium rounded-xl transition disabled:opacity-50"
            >
              {searching ? 'Searching…' : 'Search'}
            </button>
          </div>
          <p className="text-gray-500 text-xs mb-6">
            Add an issue number to jump straight to that exact issue — no need to pick a series first.
          </p>

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
          ) : huntingForIssue ? (
            <p className="text-gray-400">Looking for issue #{issueNumber.trim()}…</p>
          ) : upcNotFound ? (
            <p className="text-gray-500 italic">
              No comic found for that UPC in GCD or Metron. It may just not be cataloged yet — try searching by series title instead.
            </p>
          ) : searchedWithNumber && !browseAllOverride && noIssueAnywhere ? (
            <div>
              <p className="text-gray-500 italic mb-3">
                No issue #{issueNumber.trim()} found in any series matching "{query.trim()}".
              </p>
              {results.length > 0 && (
                <button
                  onClick={() => setBrowseAllOverride(true)}
                  className="text-sm text-brand-400 hover:text-brand-300 transition"
                >
                  Browse matching series by name instead
                </button>
              )}
            </div>
          ) : searchedWithNumber && !browseAllOverride && issueMatches.length > 0 ? (
            <div>
              <p className="text-gray-400 text-sm mb-4">
                Found issue #{issueNumber.trim()} in {issueMatches.length} matching series:
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                {issueMatches.map(({ series, issue }) => (
                  <button
                    key={`${series.provider}-${issue.provider_issue_id}`}
                    onClick={() => openIssue(series, issue)}
                    disabled={detailLoading === issue.provider_issue_id}
                    className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl overflow-hidden text-left transition disabled:opacity-50"
                  >
                    <div className="aspect-[2/3] bg-gray-800 flex items-center justify-center">
                      {issue.image ? (
                        <img src={issue.image} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <BookOpen size={28} className="text-gray-600" />
                      )}
                    </div>
                    <div className="p-3">
                      <p className="font-medium truncate">{series.name}</p>
                      <span className={`inline-block text-xs px-2 py-0.5 rounded-full mt-1 ${PROVIDER_BADGE[series.provider]}`}>
                        {PROVIDER_LABEL[series.provider]}
                      </span>
                      <p className="text-xs text-gray-500 mt-1">
                        #{issue.number}
                        {issue.legacy_number && ` (Legacy #${issue.legacy_number})`}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : hasSearched && results.length === 0 ? (
            <p className="text-gray-500 italic">No results found in either database — try a different title.</p>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                {results.map((series) => (
                  <button
                    key={`${series.provider}-${series.provider_series_id}`}
                    onClick={() => selectSeries(series)}
                    className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl overflow-hidden text-left transition"
                  >
                    <div className="aspect-[2/3] bg-gray-800 flex items-center justify-center">
                      {series.image ? (
                        <img src={series.image} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <BookOpen size={28} className="text-gray-600" />
                      )}
                    </div>
                    <div className="p-3">
                      <div className="flex items-center gap-2">
                        <p className="font-medium truncate">{series.name}</p>
                      </div>
                      <span className={`inline-block text-xs px-2 py-0.5 rounded-full mt-1 ${PROVIDER_BADGE[series.provider]}`}>
                        {PROVIDER_LABEL[series.provider]}
                      </span>
                      <p className="text-xs text-gray-500 mt-1">
                        {[series.publisher, series.start_year, series.issue_count ? `${series.issue_count} issues` : null]
                          .filter(Boolean).join(' · ')}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
              {hasMore && (
                <div ref={sentinelRef} className="text-center text-gray-500 text-sm py-6">
                  {loadingMore ? 'Loading more…' : ''}
                </div>
              )}
            </>
          )}
        </>
      )}

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
