import api from './client'
import type { CsvImportConflict } from '../types'

export const fetchCsvConflicts = () =>
  api.get<CsvImportConflict[]>('/uploads/conflicts').then(r => r.data)

export const acceptCsvConflict = (id: number) =>
  api.post<CsvImportConflict>(`/uploads/conflicts/${id}/accept`).then(r => r.data)

export const rejectCsvConflict = (id: number) =>
  api.post<CsvImportConflict>(`/uploads/conflicts/${id}/reject`).then(r => r.data)
