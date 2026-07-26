import api from './client'
import type { KioskCard, KioskSignupInput, SeriesSearchResult } from '../types'

export const submitKioskSignup = (payload: KioskSignupInput) =>
  api.post('/kiosk/signup', payload)

export const fetchTodaysPicks = () =>
  api.get<KioskCard[]>('/kiosk/featured/todays-picks').then(r => r.data)

export const fetchSignedComics = () =>
  api.get<KioskCard[]>('/kiosk/featured/signed').then(r => r.data)

export const searchKioskSeries = (q: string) =>
  api.get<SeriesSearchResult[]>('/kiosk/series/search', { params: { q } }).then(r => r.data)

export const fetchKioskSeriesItems = (name: string) =>
  api.get<KioskCard[]>('/kiosk/series/items', { params: { name } }).then(r => r.data)
