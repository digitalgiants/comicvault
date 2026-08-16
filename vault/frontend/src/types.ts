export interface Comic {
  id: number
  upc: string | null
  img: string | null
  master_photo: string | null
  publisher: string | null
  series: string
  volume: string | null
  issue_number: string | null
  legacy_number: string | null
  cover_date: string | null
  store_date: string | null
  newstand: boolean | null
  print_run: string | null
  variant: string | null
  cover_artist: string | null
  penciller: string | null
  inker: string | null
  writer: string | null
  average_price: number | null
  created_at: string
}

export interface Sale {
  id: number
  user_comic_id: number
  sell_date: string
  sell_price: number | null
  notes: string | null
  created_at: string
}

export interface SaleWithComic extends Sale {
  comic: Comic
}

export interface UserComic {
  id: number
  user_id: number
  comic_id: number
  comic: Comic
  count: number
  paid_price: number | null
  asking_price: number | null
  point_of_purchase: string | null
  buy_date: string | null
  signed: boolean
  remarked: boolean
  condition: string | null
  personal_img: string | null
  notes: string | null
  do_not_sell: boolean
  reserve_count: number
  created_at: string
  sales: Sale[]
}

export function availableCopies(uc: UserComic): number {
  return Math.max((uc.count ?? 1) - (uc.sales?.length ?? 0) - (uc.reserve_count ?? 0), 0)
}

// Priority: your own photo of your copy, then the catalog's master photo
// (if someone's photo has been promoted as the shared image), then the
// originally looked-up cover.
export function coverImage(uc: UserComic): string | null {
  return uc.personal_img ?? uc.comic.master_photo ?? uc.comic.img
}

export function latestSalePrice(uc: UserComic): number | null {
  if (!uc.sales?.length) return null
  return uc.sales[uc.sales.length - 1].sell_price ?? null
}

export interface Snapshot {
  date: string
  comic_count: number
  total_paid: number
  total_value: number
}

export interface BugReport {
  id: number
  text: string
  comic_id: number | null
  page_url: string | null
  resolved: boolean
  created_at: string
  user_username: string
  comic_name: string | null
}

export type ColumnVisibility = Record<string, boolean>

export const COLLECTION_COLUMNS: { key: string; label: string }[] = [
  { key: 'upc', label: 'UPC' },
  { key: 'img', label: 'Cover' },
  { key: 'series', label: 'Series' },
  { key: 'volume', label: 'Volume' },
  { key: 'issue_number', label: 'Issue Number' },
  { key: 'legacy_number', label: 'Lgcy Number' },
  { key: 'cover_date', label: 'Cover Date' },
  { key: 'store_date', label: 'Store Date' },
  { key: 'newstand', label: 'Newstand' },
  { key: 'publisher', label: 'Publisher' },
  { key: 'count', label: 'Count' },
  { key: 'available', label: 'Available' },
  { key: 'print_run', label: 'Print Run' },
  { key: 'variant', label: 'Variant' },
  { key: 'cover_artist', label: 'Cover Artist' },
  { key: 'penciller', label: 'Penciller' },
  { key: 'inker', label: 'Inker' },
  { key: 'writer', label: 'Writer' },
  { key: 'average_price', label: 'Average Price' },
  { key: 'paid_price', label: 'Paid Price' },
  { key: 'asking_price', label: 'Asking Price' },
  { key: 'buy_date', label: 'Buy Date' },
  { key: 'sell_price', label: 'Sell Price' },
  { key: 'point_of_purchase', label: 'Point of Purchase' },
  { key: 'signed', label: 'Signed' },
  { key: 'remarked', label: 'Remarked' },
  { key: 'condition', label: 'Condition' },
  { key: 'notes', label: 'Notes' },
  { key: 'do_not_sell', label: 'Do Not Sell' },
  { key: 'reserve_count', label: 'Reserve Count' },
]

export const SOLD_COLUMNS: { key: string; label: string }[] = [
  { key: 'sell_date', label: 'Sell Date' },
  { key: 'sell_price', label: 'Sell Price' },
  { key: 'publisher', label: 'Publisher' },
  { key: 'series', label: 'Series' },
  { key: 'volume', label: 'Volume' },
  { key: 'issue_number', label: 'Issue Number' },
  { key: 'writer', label: 'Writer' },
  { key: 'notes', label: 'Notes' },
]

export type UserComicUpdate = {
  count?: number | null
  paid_price?: number | null
  asking_price?: number | null
  point_of_purchase?: string | null
  buy_date?: string | null
  signed?: boolean
  remarked?: boolean
  condition?: string | null
  personal_img?: string | null
  notes?: string | null
  do_not_sell?: boolean
  reserve_count?: number | null
}

export const EDITABLE_FIELDS: { key: keyof UserComic; label: string; type: string }[] = [
  { key: 'count', label: 'Count', type: 'number' },
  { key: 'paid_price', label: 'Paid Price ($)', type: 'number' },
  { key: 'asking_price', label: 'Asking Price ($)', type: 'number' },
  { key: 'point_of_purchase', label: 'Point of Purchase', type: 'text' },
  { key: 'buy_date', label: 'Buy Date', type: 'date' },
  { key: 'signed', label: 'Signed', type: 'checkbox' },
  { key: 'remarked', label: 'Remarked', type: 'checkbox' },
  { key: 'condition', label: 'Condition', type: 'text' },
  { key: 'notes', label: 'Notes', type: 'textarea' },
  { key: 'do_not_sell', label: 'Do Not Sell', type: 'checkbox' },
  { key: 'reserve_count', label: 'Reserve Count (keep back from sale)', type: 'number' },
]

// --- Barcode scanning (comic-scraper lookups) ---

export interface CreditInfo {
  creator: string
  roles: string[]
}

export interface LookupResult {
  series_name: string
  series_volume: number | null
  publisher_name: string | null
  issue_number: string
  cover_date: string
  store_date: string | null
  variant_name: string | null
  cover_artists: string[]
  writers: string[]
  pencillers: string[]
  inkers: string[]
  credits: CreditInfo[]
  matched_on: 'base_upc' | 'variant_upc'
  source: 'cache' | 'metron' | 'gcd'
  metron_id: number | null
  cv_id: number | null
  gcd_id: number | null
  image: string | null
  cover_hash: string | null
}

interface LookupAttemptBase {
  id: string
  upc12: string
  ean5: string | null
  timestamp: string
}

export type LookupAttempt =
  | (LookupAttemptBase & { status: 'pending' })
  | (LookupAttemptBase & { status: 'success'; result: LookupResult })
  | (LookupAttemptBase & { status: 'not_found' })
  | (LookupAttemptBase & { status: 'error'; message: string })

export interface StagedItem {
  id: string
  upc12: string
  ean5: string | null
}

export interface BatchResultEvent {
  index: number
  upc12: string
  ean5: string | null
  status: 'success' | 'not_found' | 'error'
  result?: LookupResult
  message?: string
}

// Mirrors the backend's ComicCreate — fields a scanned lookup can pre-fill,
// editable before adding to the collection.
export interface ScanComicFields {
  publisher: string | null
  series: string
  volume: string | null
  issue_number: string | null
  legacy_number: string | null
  cover_date: string | null
  store_date: string | null
  newstand: boolean | null
  print_run: string | null
  variant: string | null
  writer: string | null
  penciller: string | null
  inker: string | null
  cover_artist: string | null
  average_price: number | null
  upc: string | null
  img: string | null
}

export interface ScanUserComicFields {
  count: number | null
  paid_price: number | null
  asking_price: number | null
  point_of_purchase: string | null
  buy_date: string | null
  signed: boolean
  remarked: boolean
  condition: string | null
  notes: string | null
}

export interface ScanAddRequest {
  comic: ScanComicFields
  user_comic: ScanUserComicFields
}

// --- Series title search (Metron + ComicVine) ---

export type Provider = 'metron' | 'comicvine' | 'gcd'

export interface ExternalSeriesResult {
  provider: Provider
  provider_series_id: string
  name: string
  publisher: string | null
  start_year: number | null
  issue_count: number | null
  image: string | null
}

export interface ExternalSeriesSearchResult {
  results: ExternalSeriesResult[]
  warnings: string[]
  has_more: boolean
}

export interface ImageCandidate {
  provider: Provider
  series_name: string
  image: string
}

export interface BackfillImageResult {
  status: 'found' | 'already_has_image' | 'not_found'
  image: string | null
}

export interface ExternalIssueSummary {
  provider: Provider
  provider_issue_id: string
  number: string | null
  cover_date: string | null
  image: string | null
}

// --- Kiosk (customer-facing) ---

export interface KioskCard {
  id: number
  series: string
  volume: string | null
  issue_number: string | null
  legacy_number: string | null
  cover_date: string | null
  publisher: string | null
  variant: string | null
  img: string | null
  cover_artist: string | null
  penciller: string | null
  inker: string | null
  writer: string | null
  newstand: boolean | null
  print_run: string | null
  average_price: number | null
  signed: boolean
  remarked: boolean
  condition: string | null
  available: number
}

export interface KioskTradingCard {
  id: number
  name: string
  game_name: string | null
  set_name: string | null
  card_number: string | null
  rarity: string | null
  img: string | null
  available: number
}

export interface SeriesSearchResult {
  name: string
  count: number
}

export interface KioskSignup {
  id: number
  first_name: string
  last_name: string
  email: string
  phone: string | null
  created_at: string
}

export interface KioskSettings {
  comics_price_threshold: number
  cards_price_threshold: number
  todays_picks_refresh_minutes: number
  signed_refresh_minutes: number
  cards_todays_picks_refresh_minutes: number
  cards_graded_refresh_minutes: number
}

export interface CsvImportConflict {
  id: number
  comic_id: number
  comic_series: string
  comic_issue_number: string | null
  field_name: string
  csv_value: string | null
  gcd_value: string | null
  created_at: string
}

export interface KioskSignupInput {
  first_name: string
  last_name: string
  email: string
  phone: string | null
}

// --- Trading cards (parallel to Comics above - see
// feature-requests/tcg_card_scanner_build_prompt.md for why this isn't a
// shared schema with comics) ---

export interface CardGame {
  id: number
  slug: string
  name: string
  logo_image_url: string | null
}

export interface TradingCard {
  id: number
  game_id: number
  set_id: number
  name: string
  card_number: string | null
  code: string | null
  rarity: string | null
  language: string | null
  description: string | null
  attributes: Record<string, unknown> | null
  image_small: string | null
  image_medium: string | null
  image_large: string | null
  master_photo: string | null
  average_price: number | null
  release_date: string | null
  created_at: string
  game_slug: string | null
  game_name: string | null
  set_name: string | null
}

export interface CardTransaction {
  id: number
  user_trading_card_id: number | null
  transaction_type: string
  transaction_date: string
  source: string | null
  counterparty: string | null
  price: number | null
  shipping: number | null
  tax: number | null
  fees: number | null
  total_cost: number | null
  notes: string | null
  created_at: string
}

export interface UserTradingCard {
  id: number
  user_id: number
  card_id: number
  card: TradingCard
  count: number
  condition: string | null
  language: string | null
  point_of_purchase: string | null
  buy_date: string | null
  paid_price: number | null
  asking_price: number | null
  for_sale: boolean
  personal_img: string | null
  notes: string | null
  do_not_sell: boolean
  reserve_count: number
  created_at: string
  sales: CardTransaction[]
}

export function availableCardCopies(uc: UserTradingCard): number {
  return Math.max((uc.count ?? 1) - (uc.sales?.length ?? 0) - (uc.reserve_count ?? 0), 0)
}

// Priority: your own photo, then the catalog's master photo, then whatever
// apitcg.com image is on file - mirrors coverImage()'s comic priority order.
export function cardCoverImage(uc: UserTradingCard): string | null {
  return uc.personal_img ?? uc.card.master_photo ?? uc.card.image_large ?? uc.card.image_medium ?? uc.card.image_small
}

export function latestCardSalePrice(uc: UserTradingCard): number | null {
  if (!uc.sales?.length) return null
  return uc.sales[uc.sales.length - 1].price ?? null
}

export const CARDS_COLUMNS: { key: string; label: string }[] = [
  { key: 'image_small', label: 'Image' },
  { key: 'name', label: 'Name' },
  { key: 'game_name', label: 'Game' },
  { key: 'set_name', label: 'Set' },
  { key: 'card_number', label: 'Card #' },
  { key: 'rarity', label: 'Rarity' },
  { key: 'count', label: 'Count' },
  { key: 'available', label: 'Available' },
  { key: 'condition', label: 'Condition' },
  { key: 'average_price', label: 'Average Price' },
  { key: 'paid_price', label: 'Paid Price' },
  { key: 'asking_price', label: 'Asking Price' },
  { key: 'point_of_purchase', label: 'Point of Purchase' },
  { key: 'buy_date', label: 'Buy Date' },
  { key: 'sell_price', label: 'Sell Price' },
  { key: 'notes', label: 'Notes' },
  { key: 'do_not_sell', label: 'Do Not Sell' },
  { key: 'reserve_count', label: 'Reserve Count' },
]

export type UserTradingCardUpdate = {
  count?: number | null
  condition?: string | null
  language?: string | null
  point_of_purchase?: string | null
  buy_date?: string | null
  paid_price?: number | null
  asking_price?: number | null
  for_sale?: boolean
  personal_img?: string | null
  notes?: string | null
  do_not_sell?: boolean
  reserve_count?: number | null
}

export const EDITABLE_CARD_FIELDS: { key: keyof UserTradingCard; label: string; type: string }[] = [
  { key: 'count', label: 'Count', type: 'number' },
  { key: 'condition', label: 'Condition', type: 'text' },
  { key: 'language', label: 'Language', type: 'text' },
  { key: 'paid_price', label: 'Paid Price ($)', type: 'number' },
  { key: 'asking_price', label: 'Asking Price ($)', type: 'number' },
  { key: 'point_of_purchase', label: 'Point of Purchase', type: 'text' },
  { key: 'buy_date', label: 'Buy Date', type: 'date' },
  { key: 'for_sale', label: 'For Sale', type: 'checkbox' },
  { key: 'notes', label: 'Notes', type: 'textarea' },
  { key: 'do_not_sell', label: 'Do Not Sell', type: 'checkbox' },
  { key: 'reserve_count', label: 'Reserve Count (keep back from sale)', type: 'number' },
]

export interface ScanCandidate {
  card: TradingCard
  variant_id: number | null
  confidence: number
  match_method: string
}

export interface IdentifyScanResponse {
  scan_id: number
  image_url: string
  detected_name: string | null
  detected_number: string | null
  detected_set: string | null
  detected_language: string | null
  detected_variant: string | null
  candidates: ScanCandidate[]
}

export function lookupResultToComicFields(result: LookupResult, upc12: string, ean5: string | null): ScanComicFields {
  return {
    publisher: result.publisher_name,
    series: result.series_name,
    volume: result.series_volume != null ? String(result.series_volume) : null,
    issue_number: result.issue_number,
    legacy_number: null,
    cover_date: result.cover_date || null,
    store_date: result.store_date,
    newstand: null,
    print_run: null,
    variant: result.variant_name,
    writer: result.writers.length ? result.writers.join(', ') : null,
    penciller: result.pencillers.length ? result.pencillers.join(', ') : null,
    inker: result.inkers.length ? result.inkers.join(', ') : null,
    cover_artist: result.cover_artists.length ? result.cover_artists.join(', ') : null,
    average_price: null,
    upc: ean5 ? `${upc12}${ean5}` : upc12,
    img: result.image,
  }
}
