import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import '../index.css' // <--- Ajustamos la ruta para que suba un nivel y encuentre el archivo

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
