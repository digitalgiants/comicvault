import { useState } from 'react'
import { submitKioskSignup } from '../../api/kiosk'

const CONFIRMATION_MESSAGE =
  'Thank you! We are excited to work with you. We hope to see you at the next show!'

export default function SignupForm() {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      await submitKioskSignup({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
      })
      setConfirmed(true)
      setFirstName('')
      setLastName('')
      setEmail('')
      setPhone('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-up failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (confirmed) {
    return (
      <section className="bg-gray-900 rounded-2xl p-6 border border-gray-800 text-center">
        <p className="text-green-400 mb-4">{CONFIRMATION_MESSAGE}</p>
        <button
          type="button"
          onClick={() => setConfirmed(false)}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm rounded-lg transition"
        >
          Sign up another guest
        </button>
      </section>
    )
  }

  return (
    <section className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
      <h2 className="font-semibold text-lg mb-4">Sign Up</h2>
      <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">First Name *</label>
          <input
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Last Name *</label>
          <input
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Email *</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Phone Number</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {error && <p className="sm:col-span-2 text-red-400 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="sm:col-span-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition"
        >
          {submitting ? 'Submitting…' : 'Sign Up'}
        </button>
      </form>
    </section>
  )
}
