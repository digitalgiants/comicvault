import { useRef, useState } from 'react'
import { ScanBarcode } from 'lucide-react'

// Most hardware scanners auto-append an Enter keystroke right after the
// digits they send - which for a UPC+EAN pair can mean Enter fires right
// after the base 12-digit stripe is read, before a separately-scanned EAN
// stripe ever arrives. So Enter (the form's onSubmit) only ever accepts a
// complete 17-digit UPC+EAN-5 - never a bare 12-or-more-but-not-17 digit
// read, no matter whether that Enter came from a human or a scanner. The
// Look Up button is the deliberate, human-only override for codes with a
// shorter (or no) add-on (a scanner can never click a button).
//
// A brief typing pause is still what decides "done typing" vs. "still
// scanning" for the settle-timer's own auto-submit, which - matching the
// same full-code-only rule - only ever fires at 17 digits.
const SETTLE_DELAY_MS = 150

interface Props {
  onSubmit: (upc12: string, ean: string | null) => void
  disabled?: boolean
}

// Whatever comes after the first 12 digits is kept in full, whether that's
// 2 (an older price/edition supplement), 5 (a standard EAN add-on), or any
// other length - GCD's own barcode matching does an exact match on the
// full digit string when one's given (see find_issue_by_upc), so dropping
// anything here would silently make some long-running series unmatchable
// down to the wrong issue instead of just failing cleanly.
function parseCode(raw: string): { upc12: string; ean: string | null } | null {
  const digits = raw.replace(/\D/g, '')
  if (digits.length < 12) return null
  return { upc12: digits.slice(0, 12), ean: digits.length > 12 ? digits.slice(12) : null }
}

export default function ScanInput({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState('')
  const [awaitingEnter, setAwaitingEnter] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const timerRef = useRef<number | undefined>(undefined)

  function submitIfValid(raw: string) {
    const parsed = parseCode(raw)
    if (!parsed) return
    onSubmit(parsed.upc12, parsed.ean)
    setValue('')
    setAwaitingEnter(false)
    inputRef.current?.focus()
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.value
    setValue(next)
    setAwaitingEnter(false)
    window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => {
      const digits = next.replace(/\D/g, '')
      if (digits.length === 17) {
        submitIfValid(next)
      } else if (digits.length >= 12) {
        // Complete-but-ambiguous - wait for Look Up instead of guessing
        // whether more digits (an add-on) are still coming.
        setAwaitingEnter(true)
      }
    }, SETTLE_DELAY_MS)
  }

  function handleFormSubmit(e: React.FormEvent) {
    // Enter - including a scanner's own auto-appended terminator - only
    // ever accepts a complete 17-digit code. Anything shorter needs the
    // Look Up button specifically (see the note above).
    e.preventDefault()
    window.clearTimeout(timerRef.current)
    const digits = value.replace(/\D/g, '')
    if (digits.length === 17) submitIfValid(value)
  }

  function handleLookUpClick() {
    // A real button click can only ever come from a deliberate human
    // action - never a scanner - so this is the one path that still
    // accepts a 12-digit (or any other length) code on purpose.
    window.clearTimeout(timerRef.current)
    submitIfValid(value)
  }

  return (
    <form onSubmit={handleFormSubmit}>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <ScanBarcode size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            ref={inputRef}
            value={value}
            onChange={handleChange}
            placeholder="Scan barcode, or type a 12-digit UPC (plus any add-on digits, if present)"
            inputMode="numeric"
            pattern="\d*"
            disabled={disabled}
            autoFocus
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
          />
        </div>
        <button
          type="button"
          onClick={handleLookUpClick}
          disabled={disabled || !value.trim()}
          className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
        >
          Look Up
        </button>
      </div>
      {awaitingEnter && (
        <p className="mt-1.5 text-xs text-amber-400">
          Barcode ready — click Look Up to accept, or keep scanning if there's more to it.
        </p>
      )}
    </form>
  )
}
