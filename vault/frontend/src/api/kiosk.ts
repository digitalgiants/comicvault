import api from './client'
import type { KioskCard, KioskSignupInput, KioskTradingCard, SeriesSearchResult } from '../types'

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

export const fetchCardsTodaysPicks = () =>
  api.get<KioskTradingCard[]>('/kiosk/cards/featured/todays-picks').then(r => r.data)

export const fetchGradedCards = () =>
  api.get<KioskTradingCard[]>('/kiosk/cards/featured/graded').then(r => r.data)

export const searchKioskCards = (q: string) =>
  api.get<SeriesSearchResult[]>('/kiosk/cards/search', { params: { q } }).then(r => r.data)

export const fetchKioskCardItems = (name: string) =>
  api.get<KioskTradingCard[]>('/kiosk/cards/items', { params: { name } }).then(r => r.data)
