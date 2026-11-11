import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

const LandingPage = lazy(() => import('./landing/LandingPage'))

// The public landing page is opt-in at /welcome; every other path boots the
// authenticated workspace exactly as before.
const isLandingPage = window.location.pathname.replace(/\/+$/, '') === '/welcome'

// Reveal animations hide their content only after this marker, so a stylesheet
// on its own never leaves a section invisible.
if (isLandingPage) document.documentElement.classList.add('js')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isLandingPage ? (
      <Suspense fallback={<div style={{ minHeight: '100vh', background: '#07080b' }} />}>
        <LandingPage />
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
)
