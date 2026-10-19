import { Suspense, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router'
import { LoadingState } from '@/components/ui/LoadingState'
import { PublicFooter } from './PublicFooter'
import { PublicHeader } from './PublicHeader'
import styles from './layout.module.css'

/** The public site: header, page, footer. Visitors see this without signing in. */
export function PublicLayout() {
  const location = useLocation()

  useEffect(() => {
    if (location.hash) {
      document.getElementById(location.hash.slice(1))?.scrollIntoView()
    } else {
      window.scrollTo?.(0, 0)
    }
  }, [location.pathname, location.hash])

  return (
    <div className={styles['publicShell']}>
      <a className={styles['skipLink']} href="#main-content">
        Skip to main content
      </a>
      <PublicHeader />
      <main id="main-content" className={styles['publicMain']}>
        <Suspense fallback={<LoadingState label="Loading" lines={3} block />}>
          <Outlet />
        </Suspense>
      </main>
      <PublicFooter />
    </div>
  )
}
