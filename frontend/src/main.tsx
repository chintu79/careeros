import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import './fonts.css'
import './index.css'

// Both roots are lazy: the authenticated workspace is not downloaded on
// /welcome, and the landing page is not downloaded everywhere else.
const LandingPage = lazy(() => import('./landing/LandingPage'))
const App = lazy(() => import('./App.tsx'))

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
      <Suspense fallback={<div style={{ minHeight: '100vh', background: '#0b0e12' }} />}>
        <App />
      </Suspense>
    )}
  </StrictMode>,
)
