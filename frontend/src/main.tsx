import '@fontsource-variable/inter'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ConfigurationError, getEnvironment } from './config/environment'
import './styles/tokens.css'
import './styles/global.css'
import './styles/utilities.css'

const container = document.getElementById('root')
if (!container) {
  throw new Error('The #root element is missing from index.html.')
}
const root = createRoot(container)

try {
  getEnvironment()
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
} catch (error) {
  // Invalid build-time configuration: say so plainly instead of rendering a broken app.
  const message = error instanceof ConfigurationError ? error.message : 'The application could not start.'
  container.textContent = `Configuration error: ${message}`
}
