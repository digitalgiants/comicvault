import { X } from 'lucide-react'
import SignupForm from './SignupForm'

interface Props {
  onClose: () => void
  onSuccess: () => void
}

export default function SignupModal({ onClose, onSuccess }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h3 className="font-semibold text-lg">Sign Up</h3>
            <p className="text-sm text-gray-400 mt-0.5">Get notified about new arrivals and events.</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          <SignupForm onSuccess={onSuccess} />
        </div>
      </div>
    </div>
  )
}
