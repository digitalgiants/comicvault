import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import GoogleSignInButton from '../components/GoogleSignInButton'

interface FormData {
  username: string
  password: string
  confirm: string
}

export default function SignupPage() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const { register, handleSubmit, formState: { isSubmitting } } = useForm<FormData>()

  const onSubmit = async (data: FormData, isCollector: boolean) => {
    setError('')
    if (data.password !== data.confirm) {
      setError('Passwords do not match')
      return
    }
    try {
      await signup(data.username, data.password, isCollector)
      navigate('/')
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Signup failed')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-3">
            <BookOpen size={48} className="text-brand-500" />
          </div>
          <h1 className="text-3xl font-bold">ComicVault</h1>
          <p className="text-gray-400 mt-1">Create your collection</p>
        </div>

        <form onSubmit={handleSubmit(data => onSubmit(data, false))} className="bg-gray-900 rounded-2xl p-8 space-y-5">
          {error && (
            <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Username</label>
            <input
              type="text"
              {...register('username', { required: true })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="yourusername"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Password</label>
            <input
              type="password"
              {...register('password', { required: true, minLength: 8 })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Min 8 characters"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Confirm Password</label>
            <input
              type="password"
              {...register('confirm', { required: true })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="••••••••"
            />
          </div>

          <div>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="submit"
                disabled
                title="Seller signups are temporarily disabled"
                className="w-full bg-brand-500 text-white font-semibold py-2.5 rounded-lg transition opacity-50 cursor-not-allowed"
              >
                Sign Up as Seller
              </button>
              <button
                type="button"
                onClick={handleSubmit(data => onSubmit(data, true))}
                disabled={isSubmitting}
                className="w-full bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg border border-gray-700 transition"
              >
                {isSubmitting ? 'Creating…' : 'Sign Up as Collector'}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-2 text-center">
              Seller signups are temporarily disabled. Collector: track your collection with sales tools hidden.
            </p>
          </div>

          <p className="text-center text-gray-400 text-sm">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-500 hover:text-brand-400">
              Sign in
            </Link>
          </p>

          <GoogleSignInButton onError={setError} />
        </form>
      </div>
    </div>
  )
}
