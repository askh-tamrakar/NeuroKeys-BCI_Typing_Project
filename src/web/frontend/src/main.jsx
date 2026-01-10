import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './styles/index.css'
import ClickSpark from './components/ui/ClickSpark'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ClickSpark
        sparkColor='var(--primary)'
        sparkSize={10}
        sparkRadius={15}
        sparkCount={8}
        duration={400}
        easing='ease-out'
        extraScale={1.0}
      >
        <App />
      </ClickSpark>
    </BrowserRouter>
  </React.StrictMode>,
)
