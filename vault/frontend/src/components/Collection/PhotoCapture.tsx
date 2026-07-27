import { useRef, useState } from 'react'
import Cropper, { type Area } from 'react-easy-crop'
import { Camera, X } from 'lucide-react'
import { uploadPersonalPhoto } from '../../api/collection'
import type { UserComic } from '../../types'

const ASPECT = 2 / 3
const OUTPUT_WIDTH = 400
const OUTPUT_HEIGHT = 600
const JPEG_QUALITY = 0.85

interface Props {
  ucId: number
  onUploaded: (uc: UserComic) => void
}

async function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

async function cropAndResize(imageSrc: string, area: Area): Promise<Blob> {
  const img = await loadImage(imageSrc)
  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT_WIDTH
  canvas.height = OUTPUT_HEIGHT
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not supported')
  ctx.drawImage(img, area.x, area.y, area.width, area.height, 0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT)
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Export failed'))), 'image/jpeg', JPEG_QUALITY)
  })
}

export default function PhotoCapture({ ucId, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [imageSrc, setImageSrc] = useState<string | null>(null)
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [croppedArea, setCroppedArea] = useState<Area | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setImageSrc(URL.createObjectURL(file))
    setCrop({ x: 0, y: 0 })
    setZoom(1)
    setCroppedArea(null)
    setError('')
    e.target.value = ''
  }

  function closeModal() {
    if (imageSrc) URL.revokeObjectURL(imageSrc)
    setImageSrc(null)
  }

  async function handleConfirm() {
    if (!imageSrc || !croppedArea) return
    setUploading(true)
    setError('')
    try {
      const blob = await cropAndResize(imageSrc, croppedArea)
      const uc = await uploadPersonalPhoto(ucId, blob)
      onUploaded(uc)
      closeModal()
    } catch {
      setError('Failed to upload photo. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileChange}
        className="hidden"
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
      >
        <Camera size={15} />
        Take / Choose Photo
      </button>

      {imageSrc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-md flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h3 className="font-semibold">Crop Photo</h3>
              <button onClick={closeModal} className="text-gray-400 hover:text-white transition">
                <X size={20} />
              </button>
            </div>

            <div className="relative w-full h-96 bg-black">
              <Cropper
                image={imageSrc}
                crop={crop}
                zoom={zoom}
                aspect={ASPECT}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={(_, pixels) => setCroppedArea(pixels)}
              />
            </div>

            <div className="px-6 py-4">
              <input
                type="range"
                min={1}
                max={3}
                step={0.01}
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
                className="w-full accent-brand-500"
              />
            </div>

            {error && <p className="px-6 text-red-400 text-sm">{error}</p>}

            <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-800">
              <button onClick={closeModal} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition">
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={uploading || !croppedArea}
                className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
              >
                {uploading ? 'Uploading…' : 'Save Photo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
