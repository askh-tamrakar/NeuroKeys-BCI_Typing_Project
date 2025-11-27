import React from 'react'

export default function Topbar({ 
  currentPage, 
  wsStatus, 
  latency, 
  onConnect, 
  onDisconnect, 
  user, 
  onLogout,
  onToggleSidebar 
}) {
  const pageNames = {
    live: 'Live Signals',
    commands: 'Commands',
    recordings: 'Recordings',
    devices: 'Devices',
    chat: 'Chat',
    mock: 'Mock Signal',
    setting: 'Settings',
    test: 'Test Page'
  }
  
  return (
    <div className="bg-white shadow px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={onToggleSidebar}
            className="text-2xl text-gray-700 hover:text-gray-900 transition"
          >
            ☰
          </button>
          <h1 className="text-xl font-bold text-gray-800">
            {pageNames[currentPage]}
          </h1>
        </div>
        
        <div className="flex items-center gap-4">
          {/* WebSocket Status */}
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg">
            <div className={`status-dot status-${wsStatus}`}></div>
            <span className="text-sm font-medium capitalize">{wsStatus}</span>
            {wsStatus === 'connected' && (
              <span className="text-xs text-gray-600">| {latency.toFixed(0)}ms</span>
            )}
          </div>
          
          {wsStatus === 'connected' ? (
            <button 
              onClick={onDisconnect}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition font-medium"
            >
              Disconnect
            </button>
          ) : (
            <button 
              onClick={onConnect}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition font-medium"
            >
              Connect
            </button>
          )}
          
          {/* User Menu */}
          <div className="flex items-center gap-2 pl-4 border-l border-gray-300">
            <span className="text-2xl">{user.avatar}</span>
            <span className="font-medium text-gray-700">{user.name}</span>
            <button 
              onClick={onLogout}
              className="ml-2 px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
