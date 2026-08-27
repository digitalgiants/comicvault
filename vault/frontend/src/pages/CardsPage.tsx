import { useEffect, useState, useCallback } from 'react'
import { Search, Pencil, DollarSign, Trash2, ChevronLeft, ChevronRight, ChevronDown, Plus, ScanLine } from 'lucide-react'
import { getCardCollection, getCardCollectionSetGroups, recordCardSale, deleteUserTradingCard, getCardColumnPrefs, getCardGames } from '../api/cards'
import { resolveImageUrl } from '../api/client'
import { availableCardCopies, cardCoverImage, latestCardSalePrice, type CardGame, type CardSetGroup, type UserTradingCard, type ColumnVisibility, visibleCardsColumns } from '../types'
import { useAuth } from '../hooks/useAuth'
import EditTradingCardModal from '../components/Cards/EditTradingCardModal'
import RecordCardSaleModal from '../components/Cards/RecordCardSaleModal'
import AddCardModal from '../components/Cards/AddCardModal'
import CardScanModal from '../components/Cards/CardScanModal'
import ColumnPicker from '../components/Collection/ColumnPicker'

const PAGE_SIZE = 200
const GROUP_PAGE_SIZE = 60

export default function CardsPage() {
  const { user } = useAuth()
  const isCollector = !!user?.is_collector
  const [items, setItems] = useState<UserTradingCard[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [cardNumberFilter, setCardNumberFilter] = useState('')
  const [setNameFilter, setSetNameFilter] = useState('')
  const [gameFilter, setGameFilter] = useState('')
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  const [editing, setEditing] = useState<UserTradingCard | null>(null)
  const [selling, setSelling] = useState<UserTradingCard | null>(null)
  const [adding, setAdding] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [visibility, setVisibility] = useState<ColumnVisibility>({})
  const [cardGames, setCardGames] = useState<CardGame[]>([])

  // Desktop browses the collection grouped by set (cards, drill in for a
  // per-set table); mobile always shows the flat item-card grid, regardless
  // of this - mirrors CollectionPage.tsx's series-grouped browsing exactly,
  // except cards group by Set (a real CardSet row) rather than comics'
  // denormalized series/publisher strings.
  const [isDesktop, setIsDesktop] = useState(() => window.matchMedia('(min-width: 640px)').matches)
  const [drilledSet, setDrilledSet] = useState<{ set_id: number; set_name: string; game_name: string | null } | null>(null)
  const [setGroups, setSetGroups] = useState<CardSetGroup[]>([])
  const [groupsTotal, setGroupsTotal] = useState(0)
  const [groupsPage, setGroupsPage] = useState(1)
  const [groupsLoading, setGroupsLoading] = useState(true)
  const [groupsError, setGroupsError] = useState<string | null>(null)

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 640px)')
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Set drill-down only exists as a desktop concept - if a drilled-in
  // desktop window gets resized down, fall back to mobile's normal
  // unscoped browsing instead of leaving it stuck showing just that set.
  useEffect(() => {
    if (!isDesktop) setDrilledSet(null)
  }, [isDesktop])

  // Card name and Card # both jump straight to a specific card, which
  // doesn't make sense against a "which sets do I own" grouped query - so
  // (unlike Set/Game, which just narrow whichever view is active) either
  // one bypasses grouping into the flat table, same role issueFilter alone
  // plays on the comics page.
  const groupedView = isDesktop && !search && !cardNumberFilter && !drilledSet

  useEffect(() => {
    getCardColumnPrefs('cards').then(p => setVisibility(p.columns))
  }, [])

  useEffect(() => {
    getCardGames().then(setCardGames)
  }, [])

  const fetchCollection = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = {
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }
      if (drilledSet) {
        params.set_id = drilledSet.set_id
      } else {
        if (search) params.name = search
        if (cardNumberFilter) params.card_number = cardNumberFilter
        if (setNameFilter) params.set_name = setNameFilter
        if (gameFilter) params.game_slug = gameFilter
      }
      const { items, total } = await getCardCollection(params)
      setItems(items)
      setTotal(total)
    } catch {
      setError('Failed to load your cards. Your collection is safe — this is a loading error, please try again.')
    } finally {
      setLoading(false)
    }
  }, [search, cardNumberFilter, setNameFilter, gameFilter, page, drilledSet])

  const fetchGroups = useCallback(async () => {
    setGroupsLoading(true)
    setGroupsError(null)
    try {
      const params: Record<string, string | number> = {
        skip: (groupsPage - 1) * GROUP_PAGE_SIZE,
        limit: GROUP_PAGE_SIZE,
      }
      if (setNameFilter) params.set_name = setNameFilter
      if (gameFilter) params.game_slug = gameFilter
      const { items, total } = await getCardCollectionSetGroups(params)
      setSetGroups(items)
      setGroupsTotal(total)
    } catch {
      setGroupsError('Failed to load your sets. Your collection is safe — this is a loading error, please try again.')
    } finally {
      setGroupsLoading(false)
    }
  }, [setNameFilter, gameFilter, groupsPage])

  useEffect(() => { if (!groupedView) fetchCollection() }, [page, drilledSet, groupedView])
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

  // Clears every filter, which flips groupedView back to true (it's derived
  // straight off these, see above) and re-fetches set groups.
  const backToSets = () => {
    setSearch('')
    setCardNumberFilter('')
    setSetNameFilter('')
    setGameFilter('')
    setGroupsPage(1)
  }

  // Single-card sets skip the drill-down table entirely (same shortcut as
  // tapping a mobile card) - fetch that one card and open Edit directly.
  // Falls back to a normal drill-down if the quick-fetch fails for any reason.
  const handleSetClick = async (g: CardSetGroup) => {
    if (g.card_count === 1) {
      try {
        const { items: single } = await getCardCollection({ set_id: g.set_id, limit: 1 })
        if (single.length === 1) {
          setEditing(single[0])
          return
        }
      } catch {
        // fall through to the normal drill-down below
      }
    }
    setDrilledSet({ set_id: g.set_id, set_name: g.set_name, game_name: g.game_name })
    setPage(1)
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const groupsPageCount = Math.max(1, Math.ceil(groupsTotal / GROUP_PAGE_SIZE))

  const columns = visibleCardsColumns(isCollector)
  const visibleCols = columns.filter(c => visibility[c.key] !== false)

  const handleDelete = async (uc: UserTradingCard) => {
    if (!confirm(`Permanently delete "${uc.card.name}" from your collection?`)) return
    await deleteUserTradingCard(uc.id)
    setItems(prev => prev.filter(i => i.id !== uc.id))
    setTotal(t => t - 1)
  }

  const handleDeletedFromModal = () => {
    if (!editing) return
    setItems(prev => prev.filter(i => i.id !== editing.id))
    setTotal(t => t - 1)
    setEditing(null)
  }

  const handleSaved = (updated: UserTradingCard) => {
    setItems(prev => prev.map(i => i.id === updated.id ? updated : i))
    setEditing(null)
  }

  const handleSaleSaved = async (ucId: number, transaction_date: string, price?: number | null, notes?: string | null) => {
    const sale = await recordCardSale(ucId, transaction_date, price, notes)
    setItems(prev => prev.map(i => i.id === ucId ? { ...i, sales: [...i.sales, sale] } : i))
    setSelling(null)
  }

  const fmt = (uc: UserTradingCard, key: string): string => {
    if (key === 'available') {
      const avail = availableCardCopies(uc)
      return `${avail}/${uc.count ?? 1}`
    }
    if (key === 'sell_price') {
      const price = latestCardSalePrice(uc)
      return price != null ? `$${price.toFixed(2)}` : '—'
    }
    if (key in uc.card) {
      const v = (uc.card as unknown as Record<string, unknown>)[key]
      if (v === null || v === undefined) return '—'
      if (key === 'average_price') return `$${Number(v).toFixed(2)}`
      return String(v)
    }
    const v = (uc as unknown as Record<string, unknown>)[key]
    if (v === null || v === undefined) return '—'
    if (key === 'paid_price' || key === 'asking_price') return `$${Number(v).toFixed(2)}`
    if (key === 'buy_date') return new Date(v as string).toLocaleDateString()
    if (key === 'for_sale' || key === 'do_not_sell') return v ? '✓' : '—'
    return String(v)
  }

  return (
    <div className="max-w-full px-4 py-8">
      <div className="sm:sticky sm:top-0 sm:z-30 sm:bg-gray-950 sm:pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <h1 className="text-2xl font-bold">My Cards</h1>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setScanning(true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition"
            >
              <ScanLine size={15} />
              Scan Card
            </button>
            <button
              onClick={() => setAdding(true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
            >
              <Plus size={15} />
              Add Card
            </button>
            {!groupedView && (
              <div className="hidden sm:block">
                <ColumnPicker page="cards" columns={columns} visibility={visibility} onChange={setVisibility} />
              </div>
            )}
          </div>
        </div>

        {drilledSet ? (
          <div className="hidden sm:flex items-center gap-3 mb-6">
            <button
              type="button"
              onClick={() => { setDrilledSet(null); setGroupsPage(1) }}
              className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition flex-shrink-0"
            >
              <ChevronLeft size={16} /> Back to Sets
            </button>
            <span className="text-gray-700">/</span>
            <h2 className="text-lg font-semibold text-white truncate">
              {drilledSet.set_name}
              {drilledSet.game_name && <span className="text-gray-400 font-normal"> · {drilledSet.game_name}</span>}
            </h2>
          </div>
        ) : (
          <>
            {!groupedView && (
              <button
                type="button"
                onClick={backToSets}
                className="hidden sm:flex items-center gap-1 text-sm text-gray-400 hover:text-white transition mb-3"
              >
                <ChevronLeft size={16} /> Back to Sets
              </button>
            )}
            <div className="flex flex-col sm:flex-row gap-3 mb-3">
              <div className="relative flex-1">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={search} onChange={e => setSearch(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && runSearch()}
                  placeholder="Search by card name…"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <input
                value={cardNumberFilter} onChange={e => setCardNumberFilter(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runSearch()}
                placeholder="Card #"
                className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-28"
              />
              <button onClick={runSearch} className="bg-brand-500 hover:bg-brand-600 text-white font-medium px-5 py-2.5 rounded-lg transition">Search</button>
            </div>

            {/* Set/Game are secondary filters - always visible on
                desktop/tablet, collapsed behind a toggle on mobile so
                Search+Card#+Search (the common "quick lookup" path) isn't
                pushed below the fold. */}
            <button
              type="button"
              onClick={() => setShowMoreFilters(v => !v)}
              className="sm:hidden flex items-center gap-1 text-xs text-gray-400 hover:text-white transition mb-3"
            >
              More filters (Set, Game)
              <ChevronDown size={12} className={`transition-transform ${showMoreFilters ? 'rotate-180' : ''}`} />
            </button>
            <div className={`${showMoreFilters ? 'flex' : 'hidden'} sm:flex flex-col sm:flex-row gap-3 mb-6`}>
              <input
                value={setNameFilter} onChange={e => setSetNameFilter(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runSearch()}
                placeholder="Set"
                className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40"
              />
              <select
                value={gameFilter} onChange={e => setGameFilter(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500 w-full sm:w-40"
              >
                <option value="">All Games</option>
                {cardGames.map(g => (
                  <option key={g.slug} value={g.slug}>{g.name}</option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>

      {groupedView ? (
        <div className="hidden sm:block">
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
          ) : setGroups.length === 0 ? (
            <div className="text-center text-gray-400 py-16">
              <p className="text-lg">No sets found.</p>
              <p className="text-sm mt-1">Click "Add Card" to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {setGroups.map(g => (
                <button
                  key={g.set_id}
                  type="button"
                  onClick={() => handleSetClick(g)}
                  className="bg-gray-900 border border-gray-800 hover:border-brand-500 rounded-xl overflow-hidden flex flex-col text-left transition"
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
                    <p className="font-medium text-white text-sm leading-snug line-clamp-2">{g.set_name}</p>
                    <p className="text-xs text-gray-400 truncate mt-0.5">{g.game_name ?? '—'}</p>
                    <span className="inline-block text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 mt-1.5">
                      {g.card_count} card{g.card_count === 1 ? '' : 's'}
                    </span>
                  </div>
                </button>
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
          <p className="text-lg">No cards found.</p>
          <p className="text-sm mt-1">Click "Add Card" to get started.</p>
        </div>
      ) : (
        <>
          {/* Mobile card list - a fixed, curated set of fields rather than
              the desktop table's full customizable column set, mirrors
              CollectionPage.tsx's mobile grid exactly. No Find Image icon -
              that's a GCD/Metron/ComicVine cover-search feature with no
              card equivalent (card images sync from apitcg.com directly). */}
          <div className="sm:hidden grid grid-cols-2 gap-3">
            {items.map(uc => {
              const avail = availableCardCopies(uc)
              return (
                <div key={uc.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
                  <button
                    type="button"
                    onClick={() => setEditing(uc)}
                    title="View / Edit"
                    className="block w-full"
                  >
                    {cardCoverImage(uc) ? (
                      <img
                        src={resolveImageUrl(cardCoverImage(uc)) ?? undefined}
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
                      {uc.card.name}{uc.card.card_number && ` #${uc.card.card_number}`}
                    </p>
                    <p className="text-xs text-gray-400 leading-snug line-clamp-2 mt-0.5">
                      {[uc.card.game_name, uc.card.set_name].filter(Boolean).join(' · ') || '—'}
                    </p>
                    <div className="flex flex-wrap items-center gap-1 mt-1.5">
                      {(uc.count ?? 1) > 1 && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">×{uc.count}</span>
                      )}
                      {!isCollector && (
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                          {avail}/{uc.count ?? 1}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-end gap-0.5 mt-auto pt-2 -mr-1">
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

          <div className="hidden sm:block overflow-x-auto rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead className="bg-gray-800 text-gray-400 uppercase text-xs">
                <tr>
                  {visibleCols.map(c => <th key={c.key} className="px-4 py-3 text-left whitespace-nowrap">{c.label}</th>)}
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {items.map(uc => {
                  const avail = availableCardCopies(uc)
                  return (
                    <tr key={uc.id} className="hover:bg-gray-800/50 transition">
                      {visibleCols.map(c => (
                        <td key={c.key} className="px-4 py-3 whitespace-nowrap text-gray-300">
                          {c.key === 'available' ? (
                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${avail > 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                              {avail}/{uc.count ?? 1}
                            </span>
                          ) : c.key === 'image_small' ? (
                            cardCoverImage(uc) ? (
                              <img
                                src={resolveImageUrl(cardCoverImage(uc)) ?? undefined}
                                alt=""
                                className="w-8 h-11 object-cover rounded border border-gray-700"
                              />
                            ) : '—'
                          ) : fmt(uc, c.key)}
                        </td>
                      ))}
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => setEditing(uc)} title="Edit" className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition">
                            <Pencil size={14} />
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
          <div className="hidden sm:flex items-center justify-between mt-4 text-sm text-gray-400">
            <span>
              Showing {(groupsPage - 1) * GROUP_PAGE_SIZE + 1}–{Math.min(groupsPage * GROUP_PAGE_SIZE, groupsTotal)} of {groupsTotal} sets
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
        <EditTradingCardModal
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
          onDeleted={handleDeletedFromModal}
        />
      )}
      {selling && (
        <RecordCardSaleModal
          item={selling}
          onClose={() => setSelling(null)}
          onSaved={handleSaleSaved}
        />
      )}
      {adding && (
        <AddCardModal
          onClose={() => setAdding(false)}
          onAdded={() => { setAdding(false); fetchCollection() }}
        />
      )}
      {scanning && (
        <CardScanModal
          onClose={() => setScanning(false)}
          onAdded={() => { setScanning(false); fetchCollection() }}
          onManualFallback={() => { setScanning(false); setAdding(true) }}
        />
      )}
    </div>
  )
}
