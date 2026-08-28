import { useState } from 'react'
import { BookOpen, Upload, ScanBarcode, Search, Mail, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

interface Step {
  icon: LucideIcon
  title: string
  body: string
}

// Every new signup is a Collector account (see SignupPage.tsx / Google
// sign-in) - none of these steps assume sales tools are available.
const STEPS: Step[] = [
  {
    icon: BookOpen,
    title: 'Welcome to ComicVault',
    body: "Here's a quick look at how to get your collection in.",
  },
  {
    icon: Upload,
    title: 'Upload your collection',
    body: 'Have a spreadsheet already? The Upload page has a downloadable CSV template and column guide to match your columns up.',
  },
  {
    icon: Search,
    title: 'Add books one at a time',
    body: 'Search by title to look up a book and add it to your collection, with details filled in automatically.',
  },
  {
    icon: ScanBarcode,
    title: 'Or scan the barcode',
    body: "Got the book in hand? Scan its UPC on the Scan page for the fastest way to add it.",
  },
  {
    icon: Mail,
    title: 'Want to sell through ComicVault?',
    body: 'Your account is set up for tracking your collection. Email andrew@comicvaults.com any time to get set up with pricing, listings, and sales tools.',
  },
]

export default function WelcomeTourModal({ onClose }: { onClose: () => void }) {
  const { markTourSeen } = useAuth()
  const [step, setStep] = useState(0)
  const isLast = step === STEPS.length - 1
  const current = STEPS[step]
  const Icon = current.icon

  const finish = () => {
    markTourSeen().catch(() => {})
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md flex flex-col">
        <div className="flex justify-end px-4 pt-4">
          <button onClick={finish} title="Skip" className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="px-8 pb-8 pt-2 text-center">
          <div className="flex justify-center mb-4">
            <div className="bg-brand-500/20 rounded-xl p-4">
              <Icon size={32} className="text-brand-500" />
            </div>
          </div>
          <h2 className="text-xl font-bold mb-2">{current.title}</h2>
          <p className="text-gray-400 text-sm leading-relaxed">{current.body}</p>
        </div>

        <div className="flex items-center justify-center gap-1.5 pb-6">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={`h-1.5 rounded-full transition-all ${i === step ? 'w-5 bg-brand-500' : 'w-1.5 bg-gray-700'}`}
            />
          ))}
        </div>

        <div className="flex items-center justify-between px-6 pb-6 gap-3">
          <button
            onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={step === 0}
            className="text-sm text-gray-400 hover:text-white transition disabled:opacity-0 disabled:pointer-events-none"
          >
            Back
          </button>
          {isLast ? (
            <button
              onClick={finish}
              className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
            >
              Get Started
            </button>
          ) : (
            <button
              onClick={() => setStep(s => Math.min(STEPS.length - 1, s + 1))}
              className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition"
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
