import { useRef, useState } from 'react'
import { ScanBarcode } from 'lucide-react'

// Hardware scanners send no terminator key, so a brief pause is what
// distinguishes "done" from "still scanning" - but auto-submit only ever
// fires at 17 digits (a complete, unambiguous 12-digit UPC + 5-digit price
// add-on). A pause at 12 or 14 is deliberately never auto-accepted, even
// though both are otherwise-valid complete codes on their own (a 12-digit
// UPC with no add-on, or the older 2-digit supplement some comics used) -
// in practice a pause there is inconsistent/ambiguous (could just be the
// gap between two separately-scanned barcode stripes on the same comic),
// so the user has to press Enter (or Look Up) to accept either deliberately.
const SETTLE_DELAY_MS = 150

interface Props {
  onSubmit: (upc12: string, ean5: string | null) => void
  disabled?: boolean
}

function parseCode(raw: string): { upc12: string; ean5: string | null } | null {
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 12) return { upc12: digits, ean5: null }
  // The 2-digit supplement isn't a real EAN5 price add-on - GCD/Metron
  // lookups only ever need the 12-digit UPC prefix, so it's just dropped
  // rather than passed through as a mis-shaped ean5 value.
  if (digits.length === 14) return { upc12: digits.slice(0, 12), ean5: null }
  if (digits.length === 17) return { upc12: digits.slice(0, 12), ean5: digits.slice(12) }
  return null
}

export default function ScanInput({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState('')
  const [awaitingEnter, setAwaitingEnter] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const timerRef = useRef<number | undefined>(undefined)

  function submitIfValid(raw: string) {
    const parsed = parseCode(raw)
    if (!parsed) return
    onSubmit(parsed.upc12, parsed.ean5)
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
      } else if (digits.length === 12 || digits.length === 14) {
        // Complete-but-ambiguous - wait for Enter instead of guessing
        // whether more digits (a price add-on) are still coming.
        setAwaitingEnter(true)
      }
    }, SETTLE_DELAY_MS)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    window.clearTimeout(timerRef.current)
    submitIfValid(value)
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <ScanBarcode size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            ref={inputRef}
            value={value}
            onChange={handleChange}
            placeholder="Scan barcode, or type a 12-digit UPC (plus a 2 or 5-digit add-on if present)"
            inputMode="numeric"
            pattern="\d*"
            disabled={disabled}
            autoFocus
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
          />
        </div>
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
        >
          Look Up
        </button>
      </div>
      {awaitingEnter && (
        <p className="mt-1.5 text-xs text-amber-400">
          Barcode ready — press Enter (or Look Up) to accept, or keep scanning if there's more to it.
        </p>
      )}
    </form>
  )
}
