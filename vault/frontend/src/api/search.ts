import api from './client'
import type { BackfillImageResult, ExternalIssueSummary, ExternalSeriesSearchResult, ImageCandidate, Provider, ScanComicFields } from '../types'

export const searchSeries = (query: string, offset = 0) =>
  api.get<ExternalSeriesSearchResult>('/search/series', { params: { query, offset } }).then(r => r.data)

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

export const getImageCandidates = (comicId: number) =>
  api.get<ImageCandidate[]>('/search/image-candidates', { params: { comic_id: comicId } }).then(r => r.data)

export const backfillImage = (comicId: number) =>
  api.post<BackfillImageResult>(`/search/backfill-image/${comicId}`).then(r => r.data)
