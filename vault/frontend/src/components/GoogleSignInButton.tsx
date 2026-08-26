import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

// Minimal shape of the Google Identity Services API this actually calls -
// loaded via the <script> tag in index.html, not an npm package.
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential: string }) => void
          }) => void
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void
        }
      }
    }
  }
}

interface Props {
  onError: (message: string) => void
}

// Renders nothing if VITE_GOOGLE_CLIENT_ID isn't set - dormant, not broken,
// matching the backend's GOOGLE_CLIENT_ID-empty-means-disabled behavior.
export default function GoogleSignInButton({ onError }: Props) {
  const { loginWithGoogle } = useAuth()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

  useEffect(() => {
    if (!clientId || !containerRef.current) return
    const container = containerRef.current

    // The GIS script tag loads async/defer, so window.google may not exist
    // yet on mount - poll briefly until it does, then render once.
    const interval = window.setInterval(() => {
      if (!window.google) return
      window.clearInterval(interval)
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async response => {
          try {
            await loginWithGoogle(response.credential)
            navigate('/')
          } catch {
            onError('Google sign-in failed. Please try again.')
          }
        },
      })
      window.google.accounts.id.renderButton(container, {
        theme: 'filled_black',
        size: 'large',
        width: 320,
      })
    }, 100)

    return () => window.clearInterval(interval)
  }, [clientId, loginWithGoogle, navigate, onError])

  if (!clientId) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-gray-800" />
        <span className="text-xs text-gray-500 uppercase">or</span>
        <div className="h-px flex-1 bg-gray-800" />
      </div>
      <div ref={containerRef} className="flex justify-center" />
    </div>
  )
}
