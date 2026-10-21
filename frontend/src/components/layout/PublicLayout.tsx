import { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router'
import { LoadingState } from '@/components/ui/LoadingState'
import { PublicFooter } from './PublicFooter'
import { PublicHeader } from './PublicHeader'
import styles from './layout.module.css'
import { LandingHeader } from '@/features/landing/LandingChrome'
import landingStyles from '@/features/landing/landing.module.css'
import authStyles from '@/features/auth/auth.module.css'
import { ThemeControl } from '@/components/ui/ThemeControl'
import type { ThemePreference } from '@/app/theme'

/** The public site: header, page, footer. Visitors see this without signing in. */
export function PublicLayout() {
  const location = useLocation()
  const isLanding = location.pathname === '/'
  const isAuth = location.pathname === '/auth/sign-in' || location.pathname === '/auth/register'
  const [publicPreference, setPublicPreference] = useState<ThemePreference>('dark')
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  const landingTheme =
    publicPreference === 'system' ? (systemDark ? 'dark' : 'light') : publicPreference
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const update = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    if (location.hash) {
      document.getElementById(location.hash.slice(1))?.scrollIntoView()
    } else {
      window.scrollTo?.(0, 0)
    }
  }, [location.pathname, location.hash])

  return (
    <div
      className={`${styles['publicShell']} ${isLanding ? landingStyles['publicLanding'] : ''} ${isAuth ? authStyles['publicAuth'] : ''}`}
      data-landing-theme={isLanding ? landingTheme : undefined}
      data-auth-theme={isAuth ? landingTheme : undefined}
    >
      <a className={styles['skipLink']} href="#main-content">
        Skip to main content
      </a>
      {isLanding ? (
        <LandingHeader
          theme={landingTheme}
          onToggle={() => setPublicPreference(landingTheme === 'dark' ? 'light' : 'dark')}
        />
      ) : (
        <PublicHeader
          appearance={
            isAuth ? (
              <ThemeControl value={publicPreference} onChange={setPublicPreference} />
            ) : undefined
          }
        />
      )}
      <main id="main-content" className={styles['publicMain']}>
        <Suspense fallback={<LoadingState label="Loading" lines={3} block />}>
          <Outlet />
        </Suspense>
      </main>
      {!isLanding ? <PublicFooter compact={isAuth} /> : null}
    </div>
  )
}
