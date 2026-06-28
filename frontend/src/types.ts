export interface Comic {
  id: number
  publisher: string | null
  name: string
  volume: string | null
  number: string | null
  print: string | null
  cover: string | null
  variant: string | null
  direct: boolean | null
  writer: string | null
  artist: string | null
  pencils: string | null
  inker: string | null
  cover_artist: string | null
  average_price: number | null
  print_ratio: string | null
  upc: string | null
  cover_image_url: string | null
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
  number_of_books: number
  price_paid: number | null
  point_of_purchase: string | null
  buy_date: string | null
  signed: boolean
  remarked: boolean
  notes: string | null
  created_at: string
  sales: Sale[]
}

export function availableCopies(uc: UserComic): number {
  return Math.max((uc.number_of_books ?? 1) - (uc.sales?.length ?? 0), 0)
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
  user_email: string
  comic_name: string | null
}

export type ColumnVisibility = Record<string, boolean>

export const COLLECTION_COLUMNS: { key: string; label: string }[] = [
  { key: 'publisher', label: 'Publisher' },
  { key: 'name', label: 'Title' },
  { key: 'volume', label: 'Volume' },
  { key: 'number', label: 'Issue #' },
  { key: 'print', label: 'Print' },
  { key: 'cover', label: 'Cover' },
  { key: 'variant', label: 'Variant' },
  { key: 'direct', label: 'Direct' },
  { key: 'writer', label: 'Writer' },
  { key: 'artist', label: 'Artist' },
  { key: 'pencils', label: 'Pencils' },
  { key: 'inker', label: 'Inker' },
  { key: 'cover_artist', label: 'Cover Artist' },
  { key: 'average_price', label: 'Avg Price' },
  { key: 'print_ratio', label: 'Print Ratio' },
  { key: 'upc', label: 'UPC' },
  { key: 'number_of_books', label: 'Qty' },
  { key: 'available', label: 'Available' },
  { key: 'price_paid', label: 'Price Paid' },
  { key: 'point_of_purchase', label: 'Purchased At' },
  { key: 'buy_date', label: 'Buy Date' },
  { key: 'signed', label: 'Signed' },
  { key: 'remarked', label: 'Remarked' },
  { key: 'notes', label: 'Notes' },
]

export const SOLD_COLUMNS: { key: string; label: string }[] = [
  { key: 'sell_date', label: 'Sell Date' },
  { key: 'sell_price', label: 'Sell Price' },
  { key: 'publisher', label: 'Publisher' },
  { key: 'name', label: 'Title' },
  { key: 'volume', label: 'Volume' },
  { key: 'number', label: 'Issue #' },
  { key: 'writer', label: 'Writer' },
  { key: 'notes', label: 'Notes' },
]

export type UserComicUpdate = {
  number_of_books?: number | null
  price_paid?: number | null
  point_of_purchase?: string | null
  buy_date?: string | null
  signed?: boolean
  remarked?: boolean
  notes?: string | null
}

export const EDITABLE_FIELDS: { key: keyof UserComic; label: string; type: string }[] = [
  { key: 'number_of_books', label: 'Qty', type: 'number' },
  { key: 'price_paid', label: 'Price Paid ($)', type: 'number' },
  { key: 'point_of_purchase', label: 'Purchased At', type: 'text' },
  { key: 'buy_date', label: 'Buy Date', type: 'date' },
  { key: 'signed', label: 'Signed', type: 'checkbox' },
  { key: 'remarked', label: 'Remarked', type: 'checkbox' },
  { key: 'notes', label: 'Notes', type: 'textarea' },
]
