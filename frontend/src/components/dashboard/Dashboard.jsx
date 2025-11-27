import React, { useState, useEffect } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../hooks/useWebSocket'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import LiveView from '../views/LiveView'
import CommandVisualizer from '../views/CommandVisualizer'
import RecordingsView from '../views/RecordingsView'
import DevicesView from '../views/DevicesView'
import ChatView from '../views/ChatView'
import MockView from '../views/MockView'
import SettingsView from '../views/SettingsView'
import TestView from '../views/TestView'

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [currentPage, setCurrentPage] = useState('live')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { status, lastMessage, latency, connect, disconnect } = useWebSocket(
    import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
  )
  

  useEffect(() => {
    connect()
  }, [])
  
  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar 
        currentPage={currentPage} 
        setCurrentPage={setCurrentPage}
        isOpen={sidebarOpen}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar
          currentPage={currentPage}
          wsStatus={status}
          latency={latency}
          onConnect={connect}
          onDisconnect={disconnect}
          user={user}
          onLogout={logout}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
        
        <div className="flex-1 overflow-y-auto p-6">
          {currentPage === 'live' && <LiveView wsData={lastMessage}/>}
          {currentPage === 'commands' && <CommandVisualizer wsData={lastMessage} />}
          {currentPage === 'recordings' && <RecordingsView />}
          {currentPage === 'devices' && <DevicesView />}
          {currentPage === 'chat' && <ChatView wsData={lastMessage} />}
          {currentPage === 'mock' && <MockView />}
          {currentPage === 'settings' && <SettingsView />}
          {currentPage === 'test' && <TestView wsData={lastMessage}/>}
        </div>
      </div>
    </div>
  )
}
