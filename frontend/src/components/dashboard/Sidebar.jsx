import React from 'react'

export default function Sidebar({ currentPage, setCurrentPage, isOpen }) {
  const pages = [
    { id: 'live', name: 'Live Signals', icon: '📊' },
    { id: 'commands', name: 'Commands', icon: '⌨️' },
    { id: 'recordings', name: 'Recordings', icon: '💾' },
    { id: 'devices', name: 'Devices', icon: '🔌' },
    { id: 'chat', name: 'Chat', icon: '💬' },
    { id: 'mock', name: 'Mock Signal Graph', icon: '📊' }, 
    { id: 'settings', name: 'Settings', icon: '⚙️' },
    { id: 'test', name: 'Test Page', icon: '⚙️'}
  ]
  
  return (
    <div className={`sidebar bg-gray-900 text-white w-64 h-full ${!isOpen && 'collapsed'}`}>
      <div className="p-4 border-b border-gray-700">
        <div className="text-2xl font-bold flex items-center gap-2">
          <span>🧠</span>
          <span>BCI Dashboard</span>
        </div>
      </div>
      
      <nav className="p-4 space-y-2">
        {pages.map(page => (
          <button
            key={page.id}
            onClick={() => setCurrentPage(page.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${
              currentPage === page.id 
                ? 'bg-blue-600 text-white' 
                : 'text-gray-300 hover:bg-gray-800'
            }`}
          >
            <span className="text-xl">{page.icon}</span>
            <span className="font-medium">{page.name}</span>
          </button>
        ))}
      </nav>
      
      <div className="absolute bottom-4 left-4 right-4 text-xs text-gray-500">
        <p>v1.0.0 • Mock Mode</p>
      </div>
    </div>
  )
}
