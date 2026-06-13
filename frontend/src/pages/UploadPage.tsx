import { useCallback, useState } from 'react'
import BugReportButton from '../components/BugReportButton'
import { useDropzone } from 'react-dropzone'
import { Upload, CheckCircle, XCircle, FileText } from 'lucide-react'
import api from '../api/client'

interface ImportResult {
  success: boolean
  filename: string
  total_rows: number
  imported: number
  failed: number
  new_comics_added_to_db: number
  existing_comics_linked: number
  errors: Array<{ row: number | string; comic: string; error: string }>
}

export default function UploadPage() {
  const [result, setResult] = useState<ImportResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

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
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    maxFiles: 1,
    disabled: uploading,
  })

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">Upload Collection</h1>
      <p className="text-gray-400 mb-8">
        Import your comics from a CSV file. Headers must match the standard column names.
      </p>

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
            </div>
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
        </div>
      )}

      <BugReportButton />

      <div className="mt-8 bg-gray-900 rounded-xl p-5 border border-gray-800">
        <h3 className="font-medium text-gray-300 mb-3">Expected CSV Columns</h3>
        <div className="flex flex-wrap gap-2">
          {[
            'publisher','name','volume','number','print','cover','variant','direct',
            'writer','artist','pencils','inker','coverArtist','numberOfBooks',
            'pricePaid','pointOfPurchase','buyDate','averagePrice','printRatio',
            'signed','remarked','notes','sellDate'
          ].map((col) => (
            <span
              key={col}
              className={`text-xs px-2 py-1 rounded font-mono ${col === 'name' ? 'bg-brand-500/30 text-brand-400 border border-brand-500/50' : 'bg-gray-800 text-gray-400'}`}
            >
              {col}
            </span>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-3">Only <span className="text-brand-400 font-mono">name</span> is required. All other columns are optional.</p>
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
