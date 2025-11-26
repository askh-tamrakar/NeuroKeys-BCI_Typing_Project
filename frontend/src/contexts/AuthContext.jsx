import React, { createContext, useState, useEffect, useContext } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    const token = localStorage.getItem('bci_token')
    const userData = localStorage.getItem('bci_user')
    if (token && userData) {
      setUser(JSON.parse(userData))
    }
    setLoading(false)
  }, [])
  
  const login = (email, password) => {
    const mockUser = { email, name: email.split('@')[0], avatar: '👤' }
    const mockToken = 'mock_jwt_token_' + Date.now()
    localStorage.setItem('bci_token', mockToken)
    localStorage.setItem('bci_user', JSON.stringify(mockUser))
    setUser(mockUser)
    return Promise.resolve(mockUser)
  }
  
  const logout = () => {
    localStorage.removeItem('bci_token')
    localStorage.removeItem('bci_user')
    setUser(null)
  }
  
  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
