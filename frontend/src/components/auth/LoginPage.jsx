import React, { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [errors, setErrors] = useState({})
  const [isSignup, setIsSignup] = useState(false)


  const handleSubmit = async (e) => {
    e.preventDefault()
    const newErrors = {}

    if (!email.includes('@')) newErrors.email = 'Invalid email'
    if (password.length < 6) newErrors.password = 'Password must be 6+ characters'

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    // --- Persistence via Vite Middleware ---
    // User requested writing to 'frontend/detail.json' via dev server

    const saveToDisk = async (payload) => {
      try {
        const res = await fetch('/_internal/save-details', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const errText = await res.text();
          alert(`Save Failed! Server returned: ${res.status}. Did you restart the terminal? Error: ${errText}`);
          console.error('Save failed details:', errText);
        } else {
          console.log('Saved to disk successfully.');
        }
      } catch (e) {
        console.error("Failed to save to disk:", e);
        alert('Connection Error: Could not reach backend middleware. Ensure "npm run dev" is running.');
      }
    }

    if (isSignup) {
      // Allow signup - sending to disk
      const payload = {
        email,
        password,
        type: 'signup',
        timestamp: Date.now()
      };

      await saveToDisk(payload);
      // alert('Account created! Details saved to detail.json.'); // Disabled per user request
      setIsSignup(false);

    } else {
      // Login Logic - Always allow entry (Demo mode) but log it to disk
      const payload = {
        email,
        password,
        type: 'login',
        timestamp: Date.now()
      };

      await saveToDisk(payload);

      // Proceed to login
      await login(email, password);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-5xl mb-4">🧠</div>
          <h1 className="text-3xl font-bold text-gray-800">BCI Dashboard</h1>
          <p className="text-gray-600 mt-2">{isSignup ? 'Create your account' : 'Sign in to access your neural interface'}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="user@example.com"
            />
            {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="••••••••"
            />
            {errors.password && <p className="text-red-500 text-sm mt-1">{errors.password}</p>}
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="w-4 h-4 text-blue-600 rounded"
            />
            <label className="ml-2 text-sm text-gray-600">Remember me</label>
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition"
          >
            {isSignup ? 'Create Account' : 'Sign In'}
          </button>

          {errors.form && <p className="text-red-500 text-sm text-center">{errors.form}</p>}

        </form>

        <p className="text-center text-sm text-gray-600 mt-6">
          {isSignup ? 'Already have an account? ' : 'Need an account? '}
          <button
            type="button"
            onClick={() => setIsSignup(!isSignup)}
            className="text-blue-600 font-bold hover:underline"
          >
            {isSignup ? 'Sign In' : 'Sign Up'}
          </button>
        </p>
      </div>
    </div>
  )
}
