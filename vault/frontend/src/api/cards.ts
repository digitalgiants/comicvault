import api from './client'
import type {
  CardGame, CardTransaction, ColumnVisibility, IdentifyScanResponse, TradingCard,
  UserTradingCard, UserTradingCardUpdate,
} from '../types'

// CPU-only Ollama inference can take a while - matches the backend's own
// IDENTIFY_TIMEOUT (100s) with headroom rather than the axios client's
// otherwise-unset default.
const IDENTIFY_TIMEOUT_MS = 115_000

export const getCardCollection = (params?: Record<string, string | number>) =>
  api.get<UserTradingCard[]>('/cards/collection', { params }).then(r => ({
    items: r.data,
    total: Number(r.headers['x-total-count'] ?? r.data.length),
  }))

export const searchCards = (params?: Record<string, string | number>) =>
  api.get<TradingCard[]>('/cards/', { params }).then(r => r.data)

export const getCardGames = () =>
  api.get<CardGame[]>('/cards/games').then(r => r.data)

export const addCardToCollection = (payload: { card_id: number } & Partial<UserTradingCardUpdate>) =>
  api.post<UserTradingCard>('/cards/collection', payload).then(r => r.data)

export const updateUserTradingCard = (id: number, update: Partial<UserTradingCardUpdate>) =>
  api.put<UserTradingCard>(`/cards/collection/${id}`, update).then(r => r.data)

export const deleteUserTradingCard = (id: number) =>
  api.delete(`/cards/collection/${id}`)

export const bulkUpdateUserTradingCards = (updates: { id: number; update: Partial<UserTradingCardUpdate> }[]) =>
  api.post<{ updated: number }>('/cards/collection/bulk', { updates }).then(r => r.data)

export const recordCardSale = (ucId: number, transaction_date: string, price?: number | null, notes?: string | null) =>
  api.post<CardTransaction>(`/cards/collection/${ucId}/sales`, { transaction_date, price, notes }).then(r => r.data)

export const updateCardSale = (ucId: number, txnId: number, price: number | null) =>
  api.put<CardTransaction>(`/cards/collection/${ucId}/sales/${txnId}`, { price }).then(r => r.data)

export const deleteCardSale = (ucId: number, txnId: number) =>
  api.delete(`/cards/collection/${ucId}/sales/${txnId}`)

export const uploadCardPersonalPhoto = (ucId: number, blob: Blob) => {
  const form = new FormData()
  form.append('file', blob, 'photo.jpg')
  return api.post<UserTradingCard>(`/cards/collection/${ucId}/photo`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const identifyCardScan = (blob: Blob) => {
  const form = new FormData()
  form.append('file', blob, 'scan.jpg')
  return api.post<IdentifyScanResponse>('/cards/scan/identify', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: IDENTIFY_TIMEOUT_MS,
  }).then(r => r.data)
}

export const confirmCardScan = (
  scanId: number,
  candidateCardId: number,
  userTradingCard: Partial<UserTradingCardUpdate>,
  variantId?: number | null,
) =>
  api.post<UserTradingCard>(`/cards/scan/${scanId}/confirm`, {
    candidate_card_id: candidateCardId,
    variant_id: variantId ?? null,
    user_trading_card: userTradingCard,
  }).then(r => r.data)

export const getCardColumnPrefs = (page: string) =>
  api.get<{ page: string; columns: ColumnVisibility }>(`/users/preferences/columns/${page}`).then(r => r.data)

export const saveCardColumnPrefs = (page: string, columns: ColumnVisibility) =>
  api.put(`/users/preferences/columns/${page}`, { columns })
