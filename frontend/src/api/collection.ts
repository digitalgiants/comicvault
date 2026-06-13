import api from './client'
import type { UserComic, UserComicUpdate, ColumnVisibility, Snapshot, BugReport } from '../types'

export const getCollection = (params?: Record<string, string>) =>
  api.get<UserComic[]>('/comics/collection', { params }).then(r => r.data)

export const getSold = (params?: Record<string, string>) =>
  api.get<UserComic[]>('/comics/sold', { params }).then(r => r.data)

export const updateUserComic = (id: number, update: Partial<UserComicUpdate>) =>
  api.put<UserComic>(`/comics/collection/${id}`, update).then(r => r.data)

export const sellUserComic = (id: number) =>
  api.patch<UserComic>(`/comics/collection/${id}/sell`).then(r => r.data)

export const deleteUserComic = (id: number) =>
  api.delete(`/comics/collection/${id}`)

export const bulkUpdateUserComics = (updates: { id: number; update: Partial<UserComicUpdate> }[]) =>
  api.post<{ updated: number }>('/comics/collection/bulk', { updates }).then(r => r.data)

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
