import { useState } from 'react'
import { Bug, X, Send } from 'lucide-react'
import { submitBugReport } from '../api/collection'
import type { UserComic } from '../types'

interface Props {
  activeComic?: UserComic | null
}

export default function BugReportButton({ activeComic }: Props) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  const handleSubmit = async () => {
    if (!text.trim()) return
    setSubmitting(true)
    try {
      await submitBugReport(text.trim(), activeComic?.comic_id, window.location.pathname)
      setDone(true)
      setText('')
      setTimeout(() => { setOpen(false); setDone(false) }, 1800)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-300 hover:text-white px-4 py-2.5 rounded-full shadow-lg transition text-sm"
      >
        <Bug size={15} />
        Report a Bug
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
              <div>
                <h3 className="font-semibold">Report a Bug</h3>
                {activeComic && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    Re: <span className="text-gray-300">{activeComic.comic.name}</span>
                  </p>
                )}
              </div>
              <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-white transition">
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
      )}
    </>
  )
}
