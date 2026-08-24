import { useState } from 'react'
import axios from 'axios'
import { X } from 'lucide-react'
import { bulkSetPublisher, bulkUpdateUserComics, recordSale, suggestBulkPublisher } from '../../api/collection'
import type { UserComic } from '../../types'
import { EDITABLE_FIELDS, availableCopies, visibleEditableFields } from '../../types'
import { useAuth } from '../../hooks/useAuth'

const SELL_PRICE_KEY = '__sell_price'
const PUBLISHER_KEY = '__publisher'

interface Props {
  selected: UserComic[]
  onClose: () => void
  onSaved: () => void
}

export default function BulkEditModal({ selected, onClose, onSaved }: Props) {
  const { user } = useAuth()
  const isCollector = !!user?.is_collector
  const [form, setForm] = useState<Record<string, unknown>>({})
  const [enabled, setEnabled] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [suggesting, setSuggesting] = useState(false)
  const [suggestMessage, setSuggestMessage] = useState('')

  const toggle = (key: string) => {
    setEnabled(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleChange = (key: string, value: unknown) => {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const handleUseGcdName = async () => {
    setSuggesting(true)
    setSuggestMessage('')
    try {
      const result = await suggestBulkPublisher(selected.map(uc => uc.id))
      if (result.status === 'suggestion' && result.publisher) {
        handleChange(PUBLISHER_KEY, result.publisher)
        setSuggestMessage(`Filled in "${result.publisher}" from GCD.`)
      } else if (result.status === 'already_correct') {
        setSuggestMessage(`"${result.publisher}" already matches GCD's name — nothing to fix.`)
      } else if (result.status === 'mixed') {
        setSuggestMessage('Selected comics have different current publishers — enter the target manually, or use the Admin Publisher report for mixed selections.')
      } else if (result.status === 'no_suggestion') {
        setSuggestMessage('No confident GCD match found — enter the target manually.')
      } else {
        setSuggestMessage('No comics selected.')
      }
    } catch (e: unknown) {
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setSuggestMessage(detail || 'Failed to look up GCD publisher.')
    } finally {
      setSuggesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const activeFields = Object.entries(enabled).filter(([, v]) => v).map(([k]) => k)
      if (!activeFields.length) { onClose(); return }

      const fieldKeys = activeFields.filter(k => k !== SELL_PRICE_KEY && k !== PUBLISHER_KEY)
      const update: Record<string, unknown> = {}
      fieldKeys.forEach(key => {
        const field = EDITABLE_FIELDS.find(f => f.key === key)
        const val = form[key]
        if (!field) return
        if (field.type === 'number') update[key] = val === '' || val === undefined ? null : Number(val)
        else if (field.type === 'checkbox') update[key] = Boolean(val)
        else if (field.type === 'date') update[key] = val === '' ? null : val
        else update[key] = val === '' ? null : val
      })

      if (fieldKeys.length) {
        await bulkUpdateUserComics(selected.map(uc => ({ id: uc.id, update })))
      }

      const warnings: string[] = []

      if (enabled[SELL_PRICE_KEY] && form[SELL_PRICE_KEY] !== undefined && form[SELL_PRICE_KEY] !== '') {
        const price = Number(form[SELL_PRICE_KEY])
        const today = new Date().toISOString()
        const sellable = selected.filter(uc => availableCopies(uc) > 0)
        await Promise.all(sellable.map(uc => recordSale(uc.id, today, price, null)))
        if (sellable.length < selected.length) {
          warnings.push(`Recorded sale for ${sellable.length} of ${selected.length} — the rest have no available copies left.`)
        }
      }

      if (enabled[PUBLISHER_KEY] && typeof form[PUBLISHER_KEY] === 'string' && form[PUBLISHER_KEY].trim()) {
        const result = await bulkSetPublisher(selected.map(uc => uc.id), form[PUBLISHER_KEY].trim())
        if (result.skipped.length > 0) {
          warnings.push(`Publisher: updated ${result.updated_comics}, skipped ${result.skipped.length} — ${result.skipped[0].reason}${result.skipped.length > 1 ? ` (+${result.skipped.length - 1} more)` : ''}`)
        }
      }

      if (warnings.length) {
        setError(warnings.join(' '))
      } else {
        onSaved()
      }
    } catch {
      setError('Failed to save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="font-semibold text-lg">Bulk Edit</h2>
            <p className="text-gray-400 text-sm">{selected.length} comics selected — only checked fields will update</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4 flex-1 space-y-3">
          {visibleEditableFields(isCollector).map(({ key, label, type, options }) => (
            <div key={key} className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={Boolean(enabled[key])}
                onChange={() => toggle(key)}
                className="mt-1 w-4 h-4 rounded accent-brand-500 flex-shrink-0"
              />
              <div className="flex-1">
                <label className="block text-sm text-gray-300 mb-1">{label}</label>
                {enabled[key] && (
                  type === 'checkbox' ? (
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(form[key])}
                        onChange={e => handleChange(key, e.target.checked)}
                        className="w-4 h-4 rounded accent-brand-500"
                      />
                      <span className="text-sm text-gray-400">{form[key] ? 'Yes' : 'No'}</span>
                    </label>
                  ) : type === 'textarea' ? (
                    <textarea
                      value={String(form[key] ?? '')}
                      onChange={e => handleChange(key, e.target.value)}
                      rows={2}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                    />
                  ) : type === 'select' ? (
                    <select
                      value={String(form[key] ?? '')}
                      onChange={e => handleChange(key, e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    >
                      <option value="">—</option>
                      {options?.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type={type}
                      value={String(form[key] ?? '')}
                      onChange={e => handleChange(key, e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  )
                )}
              </div>
            </div>
          ))}

          {!isCollector && (
            <div className="flex items-start gap-3 pt-3 border-t border-gray-800">
              <input
                type="checkbox"
                checked={Boolean(enabled[SELL_PRICE_KEY])}
                onChange={() => toggle(SELL_PRICE_KEY)}
                className="mt-1 w-4 h-4 rounded accent-brand-500 flex-shrink-0"
              />
              <div className="flex-1">
                <label className="block text-sm text-gray-300 mb-1">Sell Price ($) — records a new sale today for each</label>
                {enabled[SELL_PRICE_KEY] && (
                  <input
                    type="number"
                    step="0.01"
                    value={String(form[SELL_PRICE_KEY] ?? '')}
                    onChange={e => handleChange(SELL_PRICE_KEY, e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                )}
              </div>
            </div>
          )}

          <div className="flex items-start gap-3 pt-3 border-t border-gray-800">
            <input
              type="checkbox"
              checked={Boolean(enabled[PUBLISHER_KEY])}
              onChange={() => toggle(PUBLISHER_KEY)}
              className="mt-1 w-4 h-4 rounded accent-brand-500 flex-shrink-0"
            />
            <div className="flex-1">
              <label className="block text-sm text-gray-300 mb-1">Publisher — corrects/merges the catalog entry for each</label>
              {enabled[PUBLISHER_KEY] && (
                <>
                  <div className="flex gap-2">
                    <input
                      value={String(form[PUBLISHER_KEY] ?? '')}
                      onChange={e => handleChange(PUBLISHER_KEY, e.target.value)}
                      placeholder="e.g. DC Comics"
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                    <button
                      type="button"
                      onClick={handleUseGcdName}
                      disabled={suggesting}
                      className="flex-shrink-0 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-300 rounded-lg transition disabled:opacity-50"
                    >
                      {suggesting ? 'Looking up…' : "Use GCD's name"}
                    </button>
                  </div>
                  {suggestMessage && <p className="text-xs text-gray-500 mt-1">{suggestMessage}</p>}
                  <p className="text-xs text-gray-500 mt-1">
                    Changing this to match another comic already in the catalog merges into it, for each selected comic separately.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>

        {error && <p className="px-6 text-red-400 text-sm">{error}</p>}

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
          >
            {saving ? 'Saving…' : `Update ${selected.length} Comics`}
          </button>
        </div>
      </div>
    </div>
  )
}
