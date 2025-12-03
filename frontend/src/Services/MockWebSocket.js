export class MockWebSocket {
  constructor(url) {
    this.url = url
    this.readyState = 1 // OPEN
    this.onopen = null
    this.onmessage = null
    this.onerror = null
    this.onclose = null
    
    setTimeout(() => {
      if (this.onopen) this.onopen({ type: 'open' })
      this.startMockStream()
    }, 500)
  }
  
  startMockStream() {
    // Signal data every 40ms (25 Hz)
    this.signalInterval = setInterval(() => {
      const timestamp = Date.now()
      const data = {
        type: 'signal',
        timestamp,
        channels: {
          EEG: Array(8).fill(0).map(() => 
            Math.sin(timestamp / 1000) * 0.5 + Math.random() * 0.2 - 0.1
          ),
          EOG: Array(2).fill(0).map(() => 
            Math.sin(timestamp / 800) * 0.3 + Math.random() * 0.15 - 0.075
          ),
          EMG: Array(2).fill(0).map(() => 
            Math.random() * 0.8 - 0.4
          )
        }
      }
      if (this.onmessage) this.onmessage({ data: JSON.stringify(data) })
    }, 40)
    
    // Command data every 2-5 seconds
    this.commandInterval = setInterval(() => {
      const commands = ['A', 'B', 'C', 'D', 'E', 'ENTER', 'BACKSPACE']
      const command = commands[Math.floor(Math.random() * commands.length)]
      const data = {
        type: 'command',
        timestamp: Date.now(),
        command,
        confidence: 0.75 + Math.random() * 0.25
      }
      if (this.onmessage) this.onmessage({ data: JSON.stringify(data) })
    }, 2000 + Math.random() * 3000)
  }
  
  send(data) {
    console.log('WS Send:', data)
  }
  
  close() {
    clearInterval(this.signalInterval)
    clearInterval(this.commandInterval)
    this.readyState = 3 // CLOSED
    if (this.onclose) this.onclose({ type: 'close' })
  }
}
