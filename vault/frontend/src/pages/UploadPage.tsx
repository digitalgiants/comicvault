import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import BugReportButton from '../components/BugReportButton'
import { useDropzone } from 'react-dropzone'
import { Upload, CheckCircle, XCircle, FileText, HelpCircle, GitCompare, Search, Check, X, Download, ChevronDown } from 'lucide-react'
import api from '../api/client'
import { fetchCsvConflicts, acceptCsvConflict, rejectCsvConflict } from '../api/uploads'
import { COLLECTION_COLUMNS, type CsvImportConflict } from '../types'

interface ImportResult {
  success: boolean
  filename: string
  total_rows: number
  imported: number
  failed: number
  new_comics_added_to_db: number
  existing_comics_linked: number
  sales_recorded: number
  errors: Array<{ row: number | string; comic: string; error: string }>
  declined: Array<{ row: number | string; series: string; issue_number: string | null }>
  conflicts_queued: number
}

const FIELD_LABELS: Record<string, string> = Object.fromEntries(
  COLLECTION_COLUMNS.map(c => [c.key, c.label]),
)
const fieldLabel = (key: string) => FIELD_LABELS[key] ?? key

// Single source of truth for both the downloadable template's header row
// and the on-page Column Guide below - keeps the two from drifting apart.
// Headers are matched case-insensitively with spaces/underscores stripped
// (see csv_parser.py's _normalize_headers), so these can be readable
// Title Case without breaking the actual import.
const TEMPLATE_COLUMNS: { header: string; description: string; required?: boolean }[] = [
  { header: 'Series', description: 'Required — every other column is optional.', required: true },
  { header: 'Issue Number', description: '' },
  { header: 'Volume', description: '' },
  { header: 'Publisher', description: '' },
  { header: 'Variant', description: '' },
  { header: 'Cover Letter', description: 'e.g. "A", "B"' },
  { header: 'Legacy Number', description: '' },
  { header: 'Print Run', description: '' },
  { header: 'UPC', description: '' },
  { header: 'Cover Date', description: 'YYYY-MM-DD' },
  { header: 'Store Date', description: 'YYYY-MM-DD' },
  { header: 'Newsstand', description: 'TRUE or FALSE' },
  { header: 'Writer', description: '' },
  { header: 'Penciller', description: '' },
  { header: 'Inker', description: '' },
  { header: 'Cover Artist', description: '' },
  { header: 'Average Price', description: '' },
  { header: 'Cover Image URL', description: '' },
  { header: 'Count', description: 'Defaults to 1' },
  { header: 'Condition', description: 'Standard CGC grade, e.g. "9.4 NM" (10 Gem Mint down to 0.5 Poor)' },
  { header: 'Paid Price', description: '' },
  { header: 'Asking Price', description: '' },
  { header: 'Point of Purchase', description: '' },
  { header: 'Buy Date', description: 'YYYY-MM-DD' },
  { header: 'Signed', description: 'TRUE or FALSE' },
  { header: 'Remarked', description: 'TRUE or FALSE' },
  { header: 'Notes', description: '' },
  { header: 'Do Not Sell', description: 'TRUE or FALSE' },
  { header: 'Reserve Count', description: 'Defaults to 0' },
  { header: 'Sell Price', description: 'If set, immediately records the copy as sold' },
  { header: 'Sell Date', description: 'Defaults to today if Sell Price is set but this is blank' },
]

const downloadCsvTemplate = () => {
  const escape = (v: string) => `"${v.replace(/"/g, '""')}"`
  const csv = TEMPLATE_COLUMNS.map(c => escape(c.header)).join(',')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'comicvault-import-template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [result, setResult] = useState<ImportResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const [conflicts, setConflicts] = useState<CsvImportConflict[]>([])
  const [conflictsLoading, setConflictsLoading] = useState(true)
  const [resolvingId, setResolvingId] = useState<number | null>(null)
  const [conflictErrors, setConflictErrors] = useState<Record<number, string>>({})
  const [showColumnGuide, setShowColumnGuide] = useState(false)

  const loadConflicts = useCallback(() => {
    setConflictsLoading(true)
    fetchCsvConflicts().then(setConflicts).finally(() => setConflictsLoading(false))
  }, [])

  useEffect(() => { loadConflicts() }, [loadConflicts])

  const resolveConflict = async (id: number, accept: boolean) => {
    setResolvingId(id)
    setConflictErrors(prev => { const next = { ...prev }; delete next[id]; return next })
    try {
      await (accept ? acceptCsvConflict(id) : rejectCsvConflict(id))
      setConflicts(prev => prev.filter(c => c.id !== id))
    } catch (e: unknown) {
      // A blocked merge (e.g. the comic this conflict points at now
      // matches another comic you already own) leaves the conflict
      // pending, not silently dropped - show exactly why it failed.
      const detail = axios.isAxiosError(e) ? e.response?.data?.detail : null
      setConflictErrors(prev => ({ ...prev, [id]: detail || 'Failed to resolve this conflict. Please try again.' }))
    } finally {
      setResolvingId(null)
    }
  }

  const searchManually = (series: string, issueNumber: string | null) => {
    const params = new URLSearchParams({ series })
    if (issueNumber) params.set('issue', issueNumber)
    navigate(`/search?${params.toString()}`)
  }

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0]
    if (!file) return

    setUploading(true)
    setError('')
    setResult(null)

    const form = new FormData()
    form.append('file', file)

    try {
      const { data } = await api.post<ImportResult>('/uploads/csv', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
      if (data.conflicts_queued > 0) loadConflicts()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }, [loadConflicts])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    maxFiles: 1,
    disabled: uploading,
  })

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">Upload Collection</h1>
      <p className="text-gray-400 mb-6">
        Import your comics from a CSV file. Headers must match the standard column names.
      </p>

      <div className="mb-8 bg-gray-900 rounded-2xl border border-gray-800 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-medium text-gray-200">Not sure what columns to use?</p>
            <p className="text-sm text-gray-500 mt-0.5">Download a template with the correct headers, ready to fill in.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={downloadCsvTemplate}
              className="flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
            >
              <Download size={15} /> Download CSV Template
            </button>
            <button
              type="button"
              onClick={() => setShowColumnGuide(v => !v)}
              className="flex items-center gap-1 px-3 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition"
            >
              {showColumnGuide ? 'Hide' : 'Show'} Column Guide
              <ChevronDown size={14} className={`transition-transform ${showColumnGuide ? 'rotate-180' : ''}`} />
            </button>
          </div>
        </div>
        {showColumnGuide && (
          <div className="mt-4 pt-4 border-t border-gray-800 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-gray-500 text-xs uppercase">
                <tr>
                  <th className="text-left pb-2 pr-4">Column</th>
                  <th className="text-left pb-2">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {TEMPLATE_COLUMNS.map(c => (
                  <tr key={c.header}>
                    <td className="py-1.5 pr-4 text-gray-300 whitespace-nowrap">
                      {c.header}{c.required && <span className="text-brand-400 ml-1">*</span>}
                    </td>
                    <td className="py-1.5 text-gray-500">{c.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition
          ${isDragActive ? 'border-brand-500 bg-brand-500/10' : 'border-gray-700 hover:border-gray-500'}
          ${uploading ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input {...getInputProps()} />
        <Upload size={40} className="mx-auto text-gray-500 mb-4" />
        {uploading ? (
          <p className="text-gray-300 text-lg">Uploading…</p>
        ) : isDragActive ? (
          <p className="text-brand-400 text-lg">Drop your CSV here</p>
        ) : (
          <>
            <p className="text-gray-300 text-lg">Drag & drop a CSV, or click to browse</p>
            <p className="text-gray-500 text-sm mt-1">.csv files only, max 10MB</p>
          </>
        )}
      </div>

      {error && (
        <div className="mt-6 bg-red-900/40 border border-red-700 text-red-300 rounded-xl px-5 py-4">
          <div className="flex items-center gap-2">
            <XCircle size={18} />
            <span className="font-medium">Upload failed</span>
          </div>
          <p className="mt-1 text-sm">{error}</p>
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle size={20} className="text-green-400" />
              <h2 className="font-semibold text-lg">Import Complete</h2>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <Stat label="Total rows" value={result.total_rows} />
              <Stat label="Imported" value={result.imported} color="green" />
              <Stat label="Failed" value={result.failed} color={result.failed > 0 ? 'red' : undefined} />
              <Stat label="New comics" value={result.new_comics_added_to_db} />
              <Stat label="Matched existing" value={result.existing_comics_linked} />
              <Stat label="Sales recorded" value={result.sales_recorded} />
            </div>
            {result.conflicts_queued > 0 && (
              <p className="text-amber-400 text-sm mt-4">
                {result.conflicts_queued} field{result.conflicts_queued !== 1 ? 's' : ''} queued for review below — GCD had different data than your CSV for some new comics.
              </p>
            )}
          </div>

          {result.errors.length > 0 && (
            <div className="bg-gray-900 rounded-2xl p-6 border border-red-900/40">
              <div className="flex items-center gap-2 mb-4">
                <FileText size={18} className="text-red-400" />
                <h3 className="font-medium text-red-300">Row Errors ({result.errors.length})</h3>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {result.errors.map((e, i) => (
                  <div key={i} className="text-sm bg-gray-800 rounded-lg px-4 py-2">
                    <span className="text-gray-400">Row {e.row}</span>
                    {e.comic && <span className="text-gray-300 ml-2">— {e.comic}</span>}
                    <p className="text-red-400 mt-0.5">{e.error}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.declined.length > 0 && (
            <div className="bg-gray-900 rounded-2xl p-6 border border-amber-900/40">
              <div className="flex items-center gap-2 mb-4">
                <HelpCircle size={18} className="text-amber-400" />
                <h3 className="font-medium text-amber-300">Declined Imports ({result.declined.length})</h3>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                GCD had no matching data for these — they still imported using only what was in your CSV.
              </p>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {result.declined.map((d, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 text-sm bg-gray-800 rounded-lg px-4 py-2">
                    <div>
                      <span className="text-gray-400">Row {d.row}</span>
                      <span className="text-gray-300 ml-2">
                        {d.series}{d.issue_number ? ` #${d.issue_number}` : ''}
                      </span>
                    </div>
                    <button
                      onClick={() => searchManually(d.series, d.issue_number)}
                      className="flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 transition flex-shrink-0"
                    >
                      <Search size={12} /> Search manually
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!conflictsLoading && conflicts.length > 0 && (
        <div className="mt-6 bg-gray-900 rounded-2xl p-6 border border-blue-900/40">
          <div className="flex items-center gap-2 mb-4">
            <GitCompare size={18} className="text-blue-400" />
            <h3 className="font-medium text-blue-300">Pending Enrichment Conflicts ({conflicts.length})</h3>
          </div>
          <p className="text-xs text-gray-500 mb-3">
            GCD had different data than your CSV for these fields. Your CSV's value is already saved — accept to replace it with GCD's, or reject to keep what you have.
          </p>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {conflicts.map(c => (
              <div key={c.id} className="bg-gray-800 rounded-lg px-4 py-3">
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="text-sm text-gray-300">
                    {c.comic_series}{c.comic_issue_number ? ` #${c.comic_issue_number}` : ''}
                    <span className="text-gray-500 ml-2">— {fieldLabel(c.field_name)}</span>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button
                      onClick={() => resolveConflict(c.id, true)}
                      disabled={resolvingId === c.id}
                      title="Accept GCD's value"
                      className="p-1.5 text-gray-400 hover:text-green-400 hover:bg-gray-700 rounded-lg transition disabled:opacity-30"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={() => resolveConflict(c.id, false)}
                      disabled={resolvingId === c.id}
                      title="Reject, keep my CSV value"
                      className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded-lg transition disabled:opacity-30"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <div className="bg-gray-900 rounded px-3 py-1.5">
                    <span className="text-gray-500">Your CSV: </span>
                    <span className="text-gray-300">{c.csv_value ?? '—'}</span>
                  </div>
                  <div className="bg-gray-900 rounded px-3 py-1.5">
                    <span className="text-gray-500">GCD: </span>
                    <span className="text-gray-300">{c.gcd_value ?? '—'}</span>
                  </div>
                </div>
                {conflictErrors[c.id] && (
                  <p className="text-xs text-red-400 mt-2">{conflictErrors[c.id]}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <BugReportButton />

      <div className="mt-8 bg-gray-900 rounded-xl p-5 border border-gray-800">
        <h3 className="font-medium text-gray-300 mb-3">Expected CSV Columns</h3>
        <div className="flex flex-wrap gap-2">
          {[
            'upc','img','series','volume','issueNumber','legacyNumber','coverDate','storeDate','Newstand',
            'publisher','count','printRun','variant','coverLetter','coverArtist','penciller',
            'inker','writer','averagePrice','paidPrice','askingPrice','pointOfPurchase','buyDate',
            'sellPrice','sellDate','signed','remarked','notes','doNotSell','reserveCount'
          ].map((col) => (
            <span
              key={col}
              className={`text-xs px-2 py-1 rounded font-mono ${col === 'series' ? 'bg-brand-500/30 text-brand-400 border border-brand-500/50' : 'bg-gray-800 text-gray-400'}`}
            >
              {col}
            </span>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-3">Only <span className="text-brand-400 font-mono">series</span> is required. All other columns are optional.</p>
        <p className="text-xs text-gray-500 mt-2">
          New comics with a UPC or an exact series+issue match in GCD get blank fields filled in automatically. Fields where GCD disagrees with your CSV show up above for review, never applied automatically.
        </p>
      </div>
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color?: 'green' | 'red' }) {
  const textColor = color === 'green' ? 'text-green-400' : color === 'red' ? 'text-red-400' : 'text-white'
  return (
    <div className="bg-gray-800 rounded-xl px-4 py-3">
      <p className="text-gray-400 text-xs mb-1">{label}</p>
      <p className={`text-2xl font-bold ${textColor}`}>{value}</p>
    </div>
  )
}
