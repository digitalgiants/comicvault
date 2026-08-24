import api from './client'
import type { Comic, Sale, SaleWithComic, SeriesGroup, UserComic, UserComicUpdate, ColumnVisibility, Snapshot, BugReport } from '../types'

export const getCollection = (params?: Record<string, string | number>) =>
  api.get<UserComic[]>('/comics/collection', { params }).then(r => ({
    items: r.data,
    total: Number(r.headers['x-total-count'] ?? r.data.length),
  }))

export const getCollectionSeriesGroups = (params?: Record<string, string | number>) =>
  api.get<SeriesGroup[]>('/comics/collection/groups', { params }).then(r => ({
    items: r.data,
    total: Number(r.headers['x-total-count'] ?? r.data.length),
  }))

export const getSold = (params?: Record<string, string>) =>
  api.get<SaleWithComic[]>('/comics/sold', { params }).then(r => r.data)

export const updateUserComic = (id: number, update: Partial<UserComicUpdate>) =>
  api.put<UserComic>(`/comics/collection/${id}`, update).then(r => r.data)

export const updateComicMetadata = (comicId: number, updates: { upc?: string | null; cover_artist?: string | null; cover_letter?: string | null; volume?: string | null; publisher?: string | null; img?: string | null }) =>
  api.patch<Comic>(`/comics/${comicId}/metadata`, updates).then(r => r.data)

export const deleteUserComic = (id: number) =>
  api.delete(`/comics/collection/${id}`)

export const bulkUpdateUserComics = (updates: { id: number; update: Partial<UserComicUpdate> }[]) =>
  api.post<{ updated: number }>('/comics/collection/bulk', { updates }).then(r => r.data)

export interface PublisherSuggestResult {
  // "empty" | "mixed" | "no_suggestion" | "already_correct" | "suggestion"
  status: string
  publisher: string | null
}

export interface PublisherBulkEditResult {
  updated_comics: number
  skipped: { comic_id: number; reason: string }[]
}

export const suggestBulkPublisher = (uc_ids: number[]) =>
  api.post<PublisherSuggestResult>('/comics/collection/bulk-publisher/suggest', { uc_ids }).then(r => r.data)

export const bulkSetPublisher = (uc_ids: number[], publisher: string) =>
  api.post<PublisherBulkEditResult>('/comics/collection/bulk-publisher', { uc_ids, publisher }).then(r => r.data)

export const recordSale = (ucId: number, sell_date: string, sell_price?: number | null, notes?: string | null) =>
  api.post<Sale>(`/comics/collection/${ucId}/sales`, { sell_date, sell_price, notes }).then(r => r.data)

export const updateSale = (ucId: number, saleId: number, sell_price: number | null) =>
  api.put<Sale>(`/comics/collection/${ucId}/sales/${saleId}`, { sell_price }).then(r => r.data)

export const deleteSale = (ucId: number, saleId: number) =>
  api.delete(`/comics/collection/${ucId}/sales/${saleId}`)

export const uploadPersonalPhoto = (ucId: number, blob: Blob) => {
  const form = new FormData()
  form.append('file', blob, 'photo.jpg')
  return api.post<UserComic>(`/comics/collection/${ucId}/photo`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const getColumnPrefs = (page: string) =>
  api.get<{ page: string; columns: ColumnVisibility }>(`/users/preferences/columns/${page}`).then(r => r.data)

export const saveColumnPrefs = (page: string, columns: ColumnVisibility) =>
  api.put(`/users/preferences/columns/${page}`, { columns })

export const getSnapshots = () =>
  api.get<Snapshot[]>('/auth/snapshots').then(r => r.data)

export const submitBugReport = (text: string, comic_id?: number, page_url?: string) =>
  api.post('/bug-reports/', { text, comic_id, page_url })

export const getBugReports = (resolved?: boolean) =>
  api.get<BugReport[]>('/admin/bug-reports', { params: resolved !== undefined ? { resolved } : {} }).then(r => r.data)

export const resolveBugReport = (id: number) =>
  api.patch(`/admin/bug-reports/${id}/resolve`)
