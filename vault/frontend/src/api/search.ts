import api from './client'
import type { ExternalIssueSummary, ExternalSeriesSearchResult, Provider, ScanComicFields } from '../types'

export const searchSeries = (query: string) =>
  api.get<ExternalSeriesSearchResult>('/search/series', { params: { query } }).then(r => r.data)

export const getSeriesIssues = (provider: Provider, providerSeriesId: string) =>
  api.get<ExternalIssueSummary[]>(`/search/series/${provider}/${providerSeriesId}/issues`).then(r => r.data)

export const getIssueFields = (provider: Provider, providerIssueId: string) =>
  api.get<ScanComicFields>(`/search/issue/${provider}/${providerIssueId}`).then(r => r.data)
