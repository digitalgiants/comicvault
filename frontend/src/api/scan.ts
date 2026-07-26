import api from './client'
import type { BatchResultEvent, LookupResult, ScanAddRequest, UserComic } from '../types'

export async function lookupBarcode(upc12: string, ean5: string | null): Promise<LookupResult | null> {
  try {
    const { data } = await api.get<LookupResult>(`/scan/lookup/${upc12}`, {
      params: ean5 ? { ean5 } : {},
    })
    return data
  } catch (e: unknown) {
    if ((e as { response?: { status?: number } })?.response?.status === 404) {
      return null
    }
    throw e
  }
}

export async function addScannedComic(payload: ScanAddRequest): Promise<UserComic> {
  const { data } = await api.post<UserComic>('/scan/add', payload)
  return data
}

// Streaming SSE response needs fetch, not axios — same approach comic-scraper's own
// batchApi.ts uses (EventSource only supports GET, and this needs a request body).
export async function submitScanBatch(
  items: { upc12: string; ean5: string | null }[],
  onEvent: (event: BatchResultEvent) => void,
): Promise<void> {
  const baseURL = api.defaults.baseURL || ''
  const token = localStorage.getItem('token')

  const response = await fetch(`${baseURL}/scan/lookup/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ items }),
  })
  if (!response.ok || !response.body) {
    throw new Error(`Batch request failed with status ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let separatorIndex: number
    while ((separatorIndex = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      const dataLine = chunk.split('\n').find((line) => line.startsWith('data: '))
      if (!dataLine) continue
      onEvent(JSON.parse(dataLine.slice('data: '.length)) as BatchResultEvent)
    }
  }
}
