import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App.jsx'
import { JarvisProvider } from './context/JarvisContext.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HashRouter>
      <JarvisProvider>
        <App />
      </JarvisProvider>
    </HashRouter>
  </React.StrictMode>,
)
