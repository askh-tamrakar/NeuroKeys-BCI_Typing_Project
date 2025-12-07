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
    <div className="card h-[600px] flex flex-col bg-surface border border-border shadow-card rounded-2xl overflow-hidden">
      <div className="p-6 border-b border-border bg-bg/50 backdrop-blur-sm">
        <h2 className="text-2xl font-bold text-text flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          BCI Chat
        </h2>
        <p className="text-sm text-muted mt-1">Messages are sent automatically when ENTER command is recognized</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-hide bg-bg/30">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted space-y-4">
            <div className="w-16 h-16 rounded-full bg-surface border border-border flex items-center justify-center">
              <span className="text-2xl">💬</span>
            </div>
            <p>No messages yet. Start typing or use BCI commands!</p>
          </div>
        ) : (
          messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl p-4 shadow-sm ${msg.sender === 'user'
                  ? 'bg-primary text-primary-contrast rounded-br-none'
                  : 'bg-surface border border-border text-text rounded-bl-none'
                }`}>
                <div className="text-base">{msg.text}</div>
                <div className={`text-xs mt-2 ${msg.sender === 'user' ? 'opacity-75' : 'text-muted'}`}>
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-border bg-surface">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Type a message..."
            className="flex-1 px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all placeholder:text-muted/50"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim()}
            className="px-6 py-3 bg-primary text-primary-contrast rounded-xl font-bold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-glow hover:translate-y-[-1px] active:translate-y-[0px]"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
