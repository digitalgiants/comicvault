import { useState } from 'react'
import { X, Send } from 'lucide-react'
import { submitBugReport } from '../../api/collection'

interface Props {
  open: boolean
  onClose: () => void
}

// Global, reachable from the Navbar menu on every page - no per-page
// "active comic" context (that only ever applied on the Collection page's
// per-page floating button, which this replaces).
export default function BugReportModal({ open, onClose }: Props) {
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  if (!open) return null

  const handleSubmit = async () => {
    if (!text.trim()) return
    setSubmitting(true)
    try {
      await submitBugReport(text.trim(), undefined, window.location.pathname)
      setDone(true)
      setText('')
      setTimeout(() => { onClose(); setDone(false) }, 1800)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h3 className="font-semibold">Report a Bug</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-4">
          {done ? (
            <p className="text-green-400 text-center py-4">Thanks — report submitted!</p>
          ) : (
            <>
              <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                placeholder="Describe the issue (misspelling, wrong data, broken feature…)"
                rows={4}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                autoFocus
              />
              <div className="flex justify-end mt-3">
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !text.trim()}
                  className="flex items-center gap-2 px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                >
                  <Send size={14} />
                  {submitting ? 'Sending…' : 'Submit'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
