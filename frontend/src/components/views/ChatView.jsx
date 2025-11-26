import React, { useState, useEffect, useRef } from 'react'

export default function ChatView({ wsData }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  
  useEffect(() => {
    if (!wsData) return
    
    try {
      const parsed = JSON.parse(wsData.data)
      if (parsed.type === 'command' && parsed.command === 'ENTER') {
        // Auto-send when ENTER detected
        if (input.trim()) {
          sendMessage()
        }
      }
    } catch (e) {
      console.error('Chat parse error:', e)
    }
  }, [wsData])
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  const sendMessage = () => {
    if (!input.trim()) return
    
    const userMsg = {
      id: Date.now(),
      text: input,
      sender: 'user',
      timestamp: Date.now()
    }
    
    setMessages(prev => [...prev, userMsg])
    setInput('')
    
    // Mock bot response
    setTimeout(() => {
      const botMsg = {
        id: Date.now() + 1,
        text: `Echo: ${input}`,
        sender: 'bot',
        timestamp: Date.now()
      }
      setMessages(prev => [...prev, botMsg])
    }, 500)
  }
  
  return (
    <div className="bg-white rounded-lg shadow h-[600px] flex flex-col">
      <div className="p-4 border-b">
        <h2 className="text-2xl font-bold text-gray-800">BCI Chat</h2>
        <p className="text-sm text-gray-600">Messages are sent automatically when ENTER command is recognized</p>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-hide">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <p>No messages yet. Start typing or use BCI commands!</p>
          </div>
        ) : (
          messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`message-bubble rounded-lg p-3 ${
                msg.sender === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'
              }`}>
                <div className="text-sm">{msg.text}</div>
                <div className={`text-xs mt-1 ${msg.sender === 'user' ? 'text-blue-100' : 'text-gray-600'}`}>
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Type a message..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
