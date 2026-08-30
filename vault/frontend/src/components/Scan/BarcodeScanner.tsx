import { useEffect, useRef, useState } from 'react'
import { Camera, CameraOff } from 'lucide-react'
import { prepareZXingModule, readBarcodes, type ReadResult } from 'zxing-wasm/reader'
import wasmUrl from 'zxing-wasm/reader/zxing_reader.wasm?url'

prepareZXingModule({
  overrides: {
    locateFile: (path: string, prefix: string) => (path.endsWith('.wasm') ? wasmUrl : prefix + path),
  },
})

const SCAN_INTERVAL_MS = 300

interface Props {
  onDetected: (upc12: string, ean: string | null) => void
}

interface DetectedCode {
  upc12: string
  ean: string | null
}

// Whatever add-on digits zxing reports are kept in full - it can return a
// 2-digit EAN-2 or a 5-digit EAN-5 supplement, and clipping to a fixed
// length would silently drop a shorter one (see ScanInput.tsx's parseCode).
function extractCodes(hit: ReadResult): DetectedCode | null {
  let upc12 = hit.text
  if (hit.format === 'EAN13' && upc12.length === 13 && upc12.startsWith('0')) {
    upc12 = upc12.slice(1)
  }
  if (!/^\d{12}$/.test(upc12)) {
    return null
  }

  let ean: string | null = null
  try {
    const extra = JSON.parse(hit.extra || '{}') as { EanAddOn?: string }
    if (extra.EanAddOn && /^\d+$/.test(extra.EanAddOn)) {
      ean = extra.EanAddOn
    }
  } catch {
    // no add-on info in this read
  }

  return { upc12, ean }
}

export default function BarcodeScanner({ onDetected }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(document.createElement('canvas'))
  const userEditedRef = useRef(false)
  const [active, setActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detected, setDetected] = useState<DetectedCode | null>(null)

  useEffect(() => {
    if (!active) {
      setDetected(null)
      userEditedRef.current = false
      return
    }

    let stream: MediaStream | null = null
    let intervalId: number
    let busy = false
    let cancelled = false

    async function scanFrame() {
      const video = videoRef.current
      if (busy || !video || video.readyState < video.HAVE_CURRENT_DATA) return
      busy = true
      try {
        const canvas = canvasRef.current
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)

        const results = await readBarcodes(imageData, {
          formats: ['EANUPC'],
          eanAddOnSymbol: 'Read',
          maxNumberOfSymbols: 1,
          tryHarder: true,
        })
        const hit = results[0]
        if (!hit?.text) return

        const codes = extractCodes(hit)
        if (!codes) return

        if (userEditedRef.current) return
        setDetected((prev) =>
          // Don't let a frame that missed the add-on stomp one that already caught it.
          prev && prev.upc12 === codes.upc12 && prev.ean && !codes.ean ? prev : codes,
        )
      } catch {
        // ignore decode errors on individual frames, camera feed continues
      } finally {
        busy = false
      }
    }

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          // Narrow EAN-5 bars need more resolution than the default to resolve reliably.
          video: { facingMode: 'environment', width: { ideal: 3840 }, height: { ideal: 2160 } },
        })
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
        }
        intervalId = window.setInterval(() => void scanFrame(), SCAN_INTERVAL_MS)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not access camera')
        setActive(false)
      }
    }

    void start()
    return () => {
      cancelled = true
      window.clearInterval(intervalId)
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [active])

  function handleSubmit() {
    if (!detected) return
    onDetected(detected.upc12, detected.ean)
    setDetected(null)
    userEditedRef.current = false
  }

  function editDetected(patch: Partial<DetectedCode>) {
    userEditedRef.current = true
    setDetected((prev) => (prev ? { ...prev, ...patch } : prev))
  }

  const canSubmit =
    detected !== null &&
    /^\d{12}$/.test(detected.upc12) &&
    (detected.ean === null || /^\d+$/.test(detected.ean))

  return (
    <div className="bg-gray-900 rounded-2xl p-5 border border-gray-800">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-300">Camera Scan</h3>
        <button
          type="button"
          onClick={() => setActive((a) => !a)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
        >
          {active ? <CameraOff size={15} /> : <Camera size={15} />}
          {active ? 'Stop Scanning' : 'Start Scanning'}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

      {active && (
        <div className="rounded-xl overflow-hidden bg-black mb-3">
          <video ref={videoRef} muted playsInline className="w-full max-h-80 object-contain" />
        </div>
      )}

      {active && detected && (
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            value={detected.upc12}
            onChange={(e) => editDetected({ upc12: e.target.value.replace(/\D/g, '') })}
            inputMode="numeric"
            pattern="\d*"
            aria-label="UPC"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <input
            value={detected.ean ?? ''}
            onChange={(e) => editDetected({ ean: e.target.value.replace(/\D/g, '') || null })}
            placeholder="EAN (not found — type it in)"
            inputMode="numeric"
            pattern="\d*"
            aria-label="EAN"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
          >
            Look Up
          </button>
        </div>
      )}
    </div>
  )
}
