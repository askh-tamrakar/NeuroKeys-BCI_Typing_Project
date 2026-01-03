import React, { useEffect } from 'react';
import { AuthProvider } from './contexts/AuthContext'
import { useAuth } from './contexts/AuthContext'
import LoginPage from './components/auth/LoginPage'
import Dashboard from './components/dashboard/Dashboard'
import { soundHandler } from './handlers/SoundHandler';

function AppContent() {
  const { user, loading } = useAuth()

  // Global sound listener
  useEffect(() => {
    const handleGlobalClick = () => {
      // Only play if interaction happens, AudioContext resumes on first click
      soundHandler.resume();
      soundHandler.playClick();
    };

    // We can attach to window for general clicks, but maybe too noisy?
    // Let's attach to buttons and interactive elements via delegation if possible, 
    // or just play on any click for now as requested "soothing click sound on mouse click".
    window.addEventListener('click', handleGlobalClick);

    return () => window.removeEventListener('click', handleGlobalClick);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-2xl">Loading...</div>
      </div>
    )
  }

  return user ? <Dashboard /> : <LoginPage />
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
