import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-sans/latin-700.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { initializeTheme } from './app/theme'
import { ConfigurationError, getEnvironment } from './config/environment'
import './styles/tokens.css'
import './styles/global.css'
import './styles/utilities.css'

const container = document.getElementById('root')
if (!container) {
  throw new Error('The #root element is missing from index.html.')
}
const root = createRoot(container)
const disposeTheme = initializeTheme()
if (import.meta.hot) import.meta.hot.dispose(disposeTheme)

try {
  getEnvironment()
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
} catch (error) {
  // Invalid build-time configuration: say so plainly instead of rendering a broken app.
  const message =
    error instanceof ConfigurationError ? error.message : 'The application could not start.'
  container.textContent = `Configuration error: ${message}`
}
