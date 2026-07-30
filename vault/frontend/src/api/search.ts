import api from './client'
import type { ExternalIssueSummary, ExternalSeriesSearchResult, Provider, ScanComicFields } from '../types'

export const searchSeries = (query: string) =>
  api.get<ExternalSeriesSearchResult>('/search/series', { params: { query } }).then(r => r.data)

export const getSeriesIssues = (
  provider: Provider,
  providerSeriesId: string,
  opts?: { number?: string; seriesName?: string },
) =>
  api.get<ExternalIssueSummary[]>(`/search/series/${provider}/${providerSeriesId}/issues`, {
    params: { number: opts?.number || undefined, series_name: opts?.seriesName || undefined },
  }).then(r => r.data)

export const getIssueFields = (provider: Provider, providerIssueId: string) =>
  api.get<ScanComicFields>(`/search/issue/${provider}/${providerIssueId}`).then(r => r.data)
