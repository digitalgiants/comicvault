import { useEffect, useState, useCallback } from 'react'
import { Search, Pencil, DollarSign, Trash2, ChevronLeft, ChevronRight, ChevronDown, Image as ImageIcon, X } from 'lucide-react'
import { getCollection, getCollectionSeriesGroups, recordSale, deleteUserComic, getColumnPrefs } from '../api/collection'
import { resolveImageUrl } from '../api/client'
import { availableCopies, coverImage, latestSalePrice, type Comic, type SeriesGroup, type UserComic, type ColumnVisibility, visibleCollectionColumns } from '../types'
import { useAuth } from '../hooks/useAuth'
import EditComicModal from '../components/Collection/EditComicModal'
import BulkEditModal from '../components/Collection/BulkEditModal'
import FindImageModal from '../components/Collection/FindImageModal'
import BulkFindImagesModal from '../components/Collection/BulkFindImagesModal'
import ColumnPicker from '../components/Collection/ColumnPicker'
import BugReportButton from '../components/BugReportButton'
import RecordSaleModal from '../components/Collection/RecordSaleModal'

const PAGE_SIZE = 200
const GROUP_PAGE_SIZE = 60

export default function CollectionPage() {
  const { user } = useAuth()
  const isCollector = !!user?.is_collector
  const [items, setItems] = useState<UserComic[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [issueFilter, setIssueFilter] = useState('')
  const [publisherFilter, setPublisherFilter] = useState('')
  const [writerFilter, setWriterFilter] = useState('')
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [editing, setEditing] = useState<UserComic | null>(null)
  const [selling, setSelling] = useState<UserComic | null>(null)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [findingImage, setFindingImage] = useState<{ comicId: number; series: string; issueNumber: string | null } | null>(null)
  const [bulkFindingImages, setBulkFindingImages] = useState(false)
  const [zoomedImage, setZoomedImage] = useState<string | null>(null)
  const [visibility, setVisibility] = useState<ColumnVisibility>({})
  const [activeComic, setActiveComic] = useState<UserComic | null>(null)

  // Browses the collection grouped by series (cards, drill in for a
  // per-series table) at every screen size - same behavior on mobile,
  // tablet, and desktop.
  const [drilledSeries, setDrilledSeries] = useState<{ series: string; publisher: string | null } | null>(null)
  const [seriesGroups, setSeriesGroups] = useState<SeriesGroup[]>([])
  const [groupsTotal, setGroupsTotal] = useState(0)
  const [groupsPage, setGroupsPage] = useState(1)
  const [groupsLoading, setGroupsLoading] = useState(true)
  const [groupsError, setGroupsError] = useState<string | null>(null)

  // No issue-number search and no series drilled into = the series-card
  // landing view.
  const groupedView = !issueFilter && !drilledSeries

  useEffect(() => {
    getColumnPrefs('collection').then(p => setVisibility(p.columns))
  }, [])

  const fetchCollection = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = {
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }
      if (drilledSeries) {
        params.series_exact = drilledSeries.series
        if (drilledSeries.publisher) params.publisher_exact = drilledSeries.publisher
        else params.no_publisher = 'true'
      } else {
        if (search) params.series = search
        if (issueFilter) params.issue_number = issueFilter
        if (publisherFilter) params.publisher = publisherFilter
        if (writerFilter) params.writer = writerFilter
      }
      const { items, total } = await getCollection(params)
      setItems(items)
      setTotal(total)
    } catch {
      setError('Failed to load your collection. Your comics are safe — this is a loading error, please try again.')
    } finally {
      setLoading(false)
    }
  }, [search, issueFilter, publisherFilter, writerFilter, page, drilledSeries])

  const fetchGroups = useCallback(async () => {
    setGroupsLoading(true)
    setGroupsError(null)
    try {
      const params: Record<string, string | number> = {
        skip: (groupsPage - 1) * GROUP_PAGE_SIZE,
        limit: GROUP_PAGE_SIZE,
      }
      if (search) params.series = search
      if (publisherFilter) params.publisher = publisherFilter
      if (writerFilter) params.writer = writerFilter
      const { items, total } = await getCollectionSeriesGroups(params)
      setSeriesGroups(items)
      setGroupsTotal(total)
    } catch {
      setGroupsError('Failed to load your series. Your comics are safe — this is a loading error, please try again.')
    } finally {
      setGroupsLoading(false)
    }
  }, [search, publisherFilter, writerFilter, groupsPage])

  useEffect(() => { if (!groupedView) fetchCollection() }, [page, drilledSeries, groupedView])
  useEffect(() => { if (groupedView) fetchGroups() }, [groupsPage, groupedView])

  const runSearch = () => {
    if (groupedView) {
      if (groupsPage === 1) fetchGroups()
      else setGroupsPage(1)
    } else {
      if (page === 1) fetchCollection()
      else setPage(1)
    }
  }

  // Clears every search filter, which flips groupedView back to true (it's
  // derived straight off these, see above) and re-fetches series groups.
  const backToSeries = () => {
    setSearch('')
    setIssueFilter('')
    setPublisherFilter('')
    setWriterFilter('')
    setGroupsPage(1)
  }

  // Single-issue series skip the drill-down table entirely (same shortcut
  // as tapping a mobile card) - fetch that one book and open Edit directly.
  // Falls back to a normal drill-down if the quick-fetch fails for any reason.
  const handleSeriesClick = async (g: SeriesGroup) => {
    if (g.issue_count === 1) {
      try {
        const params: Record<string, string | number> = { series_exact: g.series, limit: 1 }
        if (g.publisher) params.publisher_exact = g.publisher
        else params.no_publisher = 'true'
        const { items: single } = await getCollection(params)
        if (single.length === 1) {
          setEditing(single[0])
          setActiveComic(single[0])
          return
        }
      } catch {
        // fall through to the normal drill-down below
      }
    }
    setDrilledSeries({ series: g.series, publisher: g.publisher })
    setPage(1)
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const groupsPageCount = Math.max(1, Math.ceil(groupsTotal / GROUP_PAGE_SIZE))

  const columns = visibleCollectionColumns(isCollector)
  const visibleCols = columns.filter(c => visibility[c.key] !== false)

  // UPC and Cover stay pinned to the left edge while scrolling horizontally
  // through the rest of the (often very wide) column set. Their order is
  // fixed by COLLECTION_COLUMNS (no column reordering exists), so img's
  // offset only ever depends on whether upc is also visible before it.
  const upcVisible = visibleCols.some(c => c.key === 'upc')
  const imgVisible = visibleCols.some(c => c.key === 'img')
  const lastFrozenKey = imgVisible ? 'img' : upcVisible ? 'upc' : null
  const frozenWidth = (key: string) => (key === 'upc' ? 'w-28' : 'w-16')
  const frozenLeft = (key: string) => (key === 'img' && upcVisible ? 'left-28' : 'left-0')
  const frozenColClass = (key: string, zIndex = 'z-10') =>
    key === 'upc' || key === 'img'
      ? `sticky ${zIndex} ${frozenLeft(key)} ${frozenWidth(key)} ${key === lastFrozenKey ? 'border-r border-gray-700' : ''} ${key === 'upc' ? 'overflow-hidden text-ellipsis' : ''}`
      : ''

  // Sticky column header (sm:+ only - stacked/wrapping on mobile makes a
  // sticky version too tall). The table wrapper below is given its own
  // bounded height + overflow-auto, making it the scroll container for
  // BOTH the frozen UPC/Cover columns (left) and this header row (top) -
  // position: sticky resolves every inset against the same nearest
  // scrolling ancestor, so top and left can't cleanly target two different
  // containers (page vs. table) on the same cell. With the table owning
  // its own scroll, top-0 here is simply "the top of that box", no pixel
  // math against the search bar's height needed.
  const STICKY_HEADER_OFFSET = 'sm:top-0'

  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelected(prev => prev.size === items.length ? new Set() : new Set(items.map(i => i.id)))
  }

  const handleDelete = async (uc: UserComic) => {
    if (!confirm(`Permanently delete "${uc.comic.series}" from your collection?`)) return
    await deleteUserComic(uc.id)
    setItems(prev => prev.filter(i => i.id !== uc.id))
    setSelected(prev => { const n = new Set(prev); n.delete(uc.id); return n })
    setTotal(t => t - 1)
  }

  const handleSaved = (updated: UserComic) => {
    setItems(prev => prev.map(i => i.id === updated.id ? updated : i))
    setEditing(null)
  }

  const handleDeletedFromModal = () => {
    if (!editing) return
    setItems(prev => prev.filter(i => i.id !== editing.id))
    setSelected(prev => { const n = new Set(prev); n.delete(editing.id); return n })
    setTotal(t => t - 1)
    setEditing(null)
  }

  const handleSaleSaved = async (ucId: number, sell_date: string, sell_price?: number | null, notes?: string | null) => {
    const sale = await recordSale(ucId, sell_date, sell_price, notes)
    setItems(prev => prev.map(i => i.id === ucId ? { ...i, sales: [...i.sales, sale] } : i))
    setSelling(null)
  }

  const handleImageSaved = (comic: Comic) => {
    // Matches on comic.id, not the row's uc.id - the catalog image is shared,
    // so every row referencing this same comic should pick up the change.
    setItems(prev => prev.map(i => i.comic.id === comic.id ? { ...i, comic } : i))
    // Also refresh the series-card thumbnail if this comic is a group's
    // representative cover - the grouped view never loads `items`, so it
    // wouldn't otherwise see the new image until the next fetchGroups().
    setSeriesGroups(prev => prev.map(g => g.cover_comic_id === comic.id ? { ...g, cover_img: comic.master_photo || comic.img } : g))
    setFindingImage(null)
  }

  const selectedItems = items.filter(i => selected.has(i.id))

  const fmt = (uc: UserComic, key: string): string => {
    if (key === 'available') {
      const avail = availableCopies(uc)
      return `${avail}/${uc.count ?? 1}`
    }
    if (key === 'sell_price') {
      const price = latestSalePrice(uc)
      return price != null ? `$${price.toFixed(2)}` : '—'
    }
    if (key in uc.comic) {
      const v = (uc.comic as unknown as Record<string, unknown>)[key]
      if (v === null || v === undefined) return '—'
      if (key === 'average_price') return `$${Number(v).toFixed(2)}`
      if (key === 'newstand') return v ? 'Yes' : 'No'
      if (key === 'cover_date' || key === 'store_date') return new Date(v as string).toLocaleDateString()
      return String(v)
    }
    const v = (uc as unknown as Record<string, unknown>)[key]
    if (v === null || v === undefined) return '—'
    if (key === 'paid_price' || key === 'asking_price') return `$${Number(v).toFixed(2)}`
    if (key === 'signed' || key === 'remarked' || key === 'do_not_sell') return v ? '✓' : '—'
    if (key === 'buy_date') return new Date(v as string).toLocaleDateString()
    return String(v)
  }

  return (
    <div className="max-w-full px-4 py-8">
      <div className="sm:sticky sm:top-0 sm:z-30 sm:bg-gray-950 sm:pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <h1 className="text-2xl font-bold">My Collection</h1>
          <div className="flex flex-wrap items-center gap-2">
            {selected.size > 0 && (
              <>
                <button
                  onClick={() => setBulkOpen(true)}
                  className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
                >
                  Bulk Edit ({selected.size})
                </button>
                <button
                  onClick={() => setBulkFindingImages(true)}
                  className="flex items-center gap-1.5 px-4 py-2 border border-gray-700 hover:border-gray-500 text-gray-300 text-sm font-medium rounded-lg transition"
                >
                  <ImageIcon size={14} /> Find Images ({selected.size})
                </button>
              </>
            )}
            {!groupedView && (
              <div className="hidden sm:block">
                <ColumnPicker page="collection" columns={columns} visibility={visibility} onChange={setVisibility} />
              </div>
            )}
          </div>
        </div>

        {drilledSeries ? (
          <div className="flex items-center gap-3 mb-6">
            <button
              type="button"
              onClick={() => { setDrilledSeries(null); setGroupsPage(1) }}
              className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition flex-shrink-0"
            >
              <ChevronLeft size={16} /> Back to Series
            </button>
            <span className="text-gray-700">/</span>
            <h2 className="text-lg font-semibold text-white truncate">
              {drilledSeries.series}
              {drilledSeries.publisher && <span className="text-gray-400 font-normal"> · {drilledSeries.publisher}</span>}
            </h2>
          </div>
        ) : (
          <>
            {!groupedView && (
              <button
                type="button"
                onClick={backToSeries}
                className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition mb-3"
              >
                <ChevronLeft size={16} /> Back to Series
              </button>
            )}
            <div className="flex flex-col sm:flex-row gap-3 mb-3">
              <div className="relative flex-1">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={search} onChange={e => setSearch(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && runSearch()}
                  placeholder="Search by title…"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <input
                value={issueFilter} onChange={e => setIssueFilter(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runSearch()}
                placeholder="Issue #"
                className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-28"
              />
              <button onClick={runSearch} className="bg-brand-500 hover:bg-brand-600 text-white font-medium px-5 py-2.5 rounded-lg transition">Search</button>
            </div>

            {/* Publisher/Writer are secondary filters - always visible on
                desktop/tablet (matches the pre-existing layout), but collapsed
                behind a toggle on mobile so Series+Issue#+Search (the common
                "quick lookup" path) isn't pushed below the fold. */}
            <button
              type="button"
              onClick={() => setShowMoreFilters(v => !v)}
              className="sm:hidden flex items-center gap-1 text-xs text-gray-400 hover:text-white transition mb-3"
            >
              More filters (Publisher, Writer)
              <ChevronDown size={12} className={`transition-transform ${showMoreFilters ? 'rotate-180' : ''}`} />
            </button>
            <div className={`${showMoreFilters ? 'flex' : 'hidden'} sm:flex flex-col sm:flex-row gap-3 mb-6`}>
              <input value={publisherFilter} onChange={e => setPublisherFilter(e.target.value)} onKeyDown={e => e.key === 'Enter' && runSearch()} placeholder="Publisher" className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40" />
              <input value={writerFilter} onChange={e => setWriterFilter(e.target.value)} onKeyDown={e => e.key === 'Enter' && runSearch()} placeholder="Writer" className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40" />
            </div>
          </>
        )}
      </div>

      {groupedView ? (
        <div>
          {groupsLoading ? (
            <div className="text-center text-gray-400 py-16">Loading…</div>
          ) : groupsError ? (
            <div className="text-center py-16">
              <p className="text-lg text-red-400">{groupsError}</p>
              <button
                onClick={fetchGroups}
                className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
              >
                Retry
              </button>
            </div>
          ) : seriesGroups.length === 0 ? (
            <div className="text-center text-gray-400 py-16">
              <p className="text-lg">No series found.</p>
              <p className="text-sm mt-1">Upload a CSV to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {seriesGroups.map(g => (
                <div
                  key={`${g.series}|${g.publisher ?? ''}`}
                  className="group relative bg-gray-900 border border-gray-800 hover:border-brand-500 rounded-xl overflow-hidden flex flex-col transition"
                >
                  <button
                    type="button"
                    onClick={() => handleSeriesClick(g)}
                    className="flex flex-col text-left flex-1"
                  >
                    {g.cover_img ? (
                      <img
                        src={resolveImageUrl(g.cover_img) ?? undefined}
                        alt=""
                        className="w-full aspect-[2/3] object-cover"
                      />
                    ) : (
                      <div className="w-full aspect-[2/3] bg-gray-800 flex items-center justify-center text-gray-600 text-xs text-center px-2">
                        No Cover
                      </div>
                    )}
                    <div className="p-2.5">
                      <p className="font-medium text-white text-sm leading-snug line-clamp-2">{g.series}</p>
                      <p className="text-xs text-gray-400 truncate mt-0.5">{g.publisher ?? '—'}</p>
                      <span className="inline-block text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 mt-1.5">
                        {g.issue_count} issue{g.issue_count === 1 ? '' : 's'}
                      </span>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setFindingImage({ comicId: g.cover_comic_id, series: g.series, issueNumber: g.cover_issue_number })}
                    title="Find Image"
                    className="absolute top-1.5 right-1.5 p-1.5 rounded-lg bg-gray-950/80 text-gray-300 opacity-100 lg:opacity-0 lg:group-hover:opacity-100 hover:text-white hover:bg-gray-900 transition"
                  >
                    <ImageIcon size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : loading ? (
        <div className="text-center text-gray-400 py-16">Loading…</div>
      ) : error ? (
        <div className="text-center py-16">
          <p className="text-lg text-red-400">{error}</p>
          <button
            onClick={fetchCollection}
            className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
          >
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center text-gray-400 py-16">
          <p className="text-lg">No comics found.</p>
          <p className="text-sm mt-1">Upload a CSV to get started.</p>
        </div>
      ) : (
        <>
          {/* Mobile card list - a fixed, curated set of fields rather than
              the desktop table's full customizable column set, since a
              dense multi-column table is a poor fit for a phone screen
              (horizontal scroll on every row). Shares selection/edit/sell/
              delete state and handlers with the desktop table below. */}
          <div className="sm:hidden grid grid-cols-2 gap-3">
            {items.map(uc => {
              const avail = availableCopies(uc)
              return (
                <div key={uc.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
                  <button
                    type="button"
                    onClick={() => { setEditing(uc); setActiveComic(uc) }}
                    title="View / Edit"
                    className="block w-full"
                  >
                    {coverImage(uc) ? (
                      <img
                        src={resolveImageUrl(coverImage(uc)) ?? undefined}
                        alt=""
                        className="w-full aspect-[2/3] object-cover"
                      />
                    ) : (
                      <div className="w-full aspect-[2/3] bg-gray-800 flex items-center justify-center text-gray-600 text-xs text-center px-2">
                        No Cover
                      </div>
                    )}
                  </button>
                  <div className="p-2.5 flex-1 flex flex-col">
                    <p className="font-medium text-white text-sm leading-snug line-clamp-2">
                      {uc.comic.series}{uc.comic.issue_number && ` #${uc.comic.issue_number}`}
                    </p>
                    <p className="text-xs text-gray-400 leading-snug line-clamp-2 mt-0.5">
                      {[uc.comic.publisher, uc.comic.volume && `Vol. ${uc.comic.volume}`].filter(Boolean).join(' · ') || '—'}
                    </p>
                    <div className="flex flex-wrap items-center gap-1 mt-1.5">
                      {(uc.count ?? 1) > 1 && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">×{uc.count}</span>
                      )}
                      {uc.signed && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-400">Signed</span>
                      )}
                      {uc.remarked && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-400">Remarked</span>
                      )}
                      {!isCollector && (
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                          {avail}/{uc.count ?? 1}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-end gap-0.5 mt-auto pt-2 -mr-1">
                      <button onClick={() => setFindingImage({ comicId: uc.comic.id, series: uc.comic.series, issueNumber: uc.comic.issue_number })} title="Find Image" className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition">
                        <ImageIcon size={14} />
                      </button>
                      {!isCollector && (
                        <button
                          onClick={() => setSelling(uc)}
                          title={uc.do_not_sell ? 'Marked Do Not Sell' : 'Record Sale'}
                          disabled={avail === 0 || uc.do_not_sell}
                          className="p-1.5 text-gray-400 hover:text-green-400 hover:bg-gray-800 rounded-lg transition disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <DollarSign size={14} />
                        </button>
                      )}
                      <button onClick={() => handleDelete(uc)} title="Delete" className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded-lg transition">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="hidden sm:block overflow-auto rounded-xl border border-gray-800 sm:max-h-[calc(100vh-230px)]">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
              <tr>
                <th className={`px-3 py-3 bg-gray-800 sm:sticky ${STICKY_HEADER_OFFSET} sm:z-20`}>
                  <input type="checkbox" checked={selected.size === items.length && items.length > 0} onChange={toggleAll} className="w-3.5 h-3.5 rounded accent-brand-500" />
                </th>
                {visibleCols.map(c => (
                  <th
                    key={c.key}
                    className={`px-4 py-3 text-left whitespace-nowrap bg-gray-800 sm:sticky ${STICKY_HEADER_OFFSET} sm:z-20 ${frozenColClass(c.key, 'z-10 sm:z-30')}`}
                  >
                    {c.label}
                  </th>
                ))}
                <th className={`px-4 py-3 text-right bg-gray-800 sm:sticky ${STICKY_HEADER_OFFSET} sm:z-20`}>Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {items.map(uc => {
                const avail = availableCopies(uc)
                return (
                  <tr key={uc.id} className={`group hover:bg-gray-800/50 transition ${selected.has(uc.id) ? 'bg-gray-800/30' : ''}`}>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1.5">
                        <input type="checkbox" checked={selected.has(uc.id)} onChange={() => toggleSelect(uc.id)} className="w-3.5 h-3.5 rounded accent-brand-500" />
                        <button onClick={() => { setEditing(uc); setActiveComic(uc) }} title="Edit" className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition">
                          <Pencil size={14} />
                        </button>
                      </div>
                    </td>
                    {visibleCols.map(c => (
                      <td
                        key={c.key}
                        className={`px-4 py-3 whitespace-nowrap text-gray-300 ${frozenColClass(c.key)} ${
                          c.key === 'upc' || c.key === 'img'
                            ? selected.has(uc.id) ? 'bg-gray-800' : 'bg-gray-950 group-hover:bg-gray-900'
                            : ''
                        }`}
                      >
                        {c.key === 'available' ? (
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                            {avail}/{uc.count ?? 1}
                          </span>
                        ) : c.key === 'img' ? (
                          coverImage(uc) ? (
                            <button
                              type="button"
                              onClick={() => setZoomedImage(resolveImageUrl(coverImage(uc)))}
                              title="View larger"
                              className="block"
                            >
                              <img
                                src={resolveImageUrl(coverImage(uc)) ?? undefined}
                                alt=""
                                className="w-8 h-11 object-cover rounded border border-gray-700 hover:border-brand-500 transition cursor-zoom-in"
                              />
                            </button>
                          ) : '—'
                        ) : fmt(uc, c.key)}
                      </td>
                    ))}
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setFindingImage({ comicId: uc.comic.id, series: uc.comic.series, issueNumber: uc.comic.issue_number })} title="Find Image" className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition">
                          <ImageIcon size={14} />
                        </button>
                        {!isCollector && (
                          <button
                            onClick={() => setSelling(uc)}
                            title={uc.do_not_sell ? 'Marked Do Not Sell' : 'Record Sale'}
                            disabled={avail === 0 || uc.do_not_sell}
                            className="p-1.5 text-gray-400 hover:text-green-400 hover:bg-gray-700 rounded-lg transition disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            <DollarSign size={14} />
                          </button>
                        )}
                        <button onClick={() => handleDelete(uc)} title="Delete" className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded-lg transition">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
        </>
      )}

      {groupedView ? (
        !groupsLoading && groupsTotal > 0 && (
          <div className="flex items-center justify-between mt-4 text-sm text-gray-400">
            <span>
              Showing {(groupsPage - 1) * GROUP_PAGE_SIZE + 1}–{Math.min(groupsPage * GROUP_PAGE_SIZE, groupsTotal)} of {groupsTotal} series
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setGroupsPage(p => Math.max(1, p - 1))}
                disabled={groupsPage === 1}
                className="p-2 rounded-lg border border-gray-700 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition"
              >
                <ChevronLeft size={16} />
              </button>
              <span>Page {groupsPage} of {groupsPageCount}</span>
              <button
                onClick={() => setGroupsPage(p => Math.min(groupsPageCount, p + 1))}
                disabled={groupsPage === groupsPageCount}
                className="p-2 rounded-lg border border-gray-700 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )
      ) : (
        !loading && total > 0 && (
          <div className="flex items-center justify-between mt-4 text-sm text-gray-400">
            <span>
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg border border-gray-700 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition"
              >
                <ChevronLeft size={16} />
              </button>
              <span>Page {page} of {pageCount}</span>
              <button
                onClick={() => setPage(p => Math.min(pageCount, p + 1))}
                disabled={page === pageCount}
                className="p-2 rounded-lg border border-gray-700 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )
      )}

      {editing && (
        <EditComicModal
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
          onItemChange={updated => setItems(prev => prev.map(i => i.id === updated.id ? updated : i))}
          onDeleted={handleDeletedFromModal}
        />
      )}
      {selling && (
        <RecordSaleModal
          item={selling}
          onClose={() => setSelling(null)}
          onSaved={handleSaleSaved}
        />
      )}
      {bulkOpen && <BulkEditModal selected={selectedItems} onClose={() => setBulkOpen(false)} onSaved={() => { setBulkOpen(false); setSelected(new Set()); fetchCollection() }} />}
      {findingImage && (
        <FindImageModal
          comicId={findingImage.comicId}
          series={findingImage.series}
          issueNumber={findingImage.issueNumber}
          onClose={() => setFindingImage(null)}
          onSaved={handleImageSaved}
        />
      )}
      {bulkFindingImages && (
        <BulkFindImagesModal
          selected={selectedItems}
          onClose={() => { setBulkFindingImages(false); setSelected(new Set()); fetchCollection() }}
        />
      )}
      {zoomedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 cursor-zoom-out"
          onClick={() => setZoomedImage(null)}
        >
          <button
            onClick={() => setZoomedImage(null)}
            className="absolute top-4 right-4 text-gray-300 hover:text-white transition"
          >
            <X size={28} />
          </button>
          <img
            src={zoomedImage}
            alt=""
            className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
      <BugReportButton activeComic={activeComic} />
    </div>
  )
}
