import { Suspense, useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router'
import { LoadingState } from '@/components/ui/LoadingState'
import { MobileNavigation } from './MobileNavigation'
import { ServiceStatusBanner } from './ServiceStatusBanner'
import { Sidebar } from './Sidebar'
import styles from './layout.module.css'

/** The signed-in workspace: navy sidebar on wide screens, top bar and drawer on narrow ones, one main region. */
export function WorkspaceLayout() {
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const isFirstRender = useRef(true)

  // Move focus to the new page after a route change so keyboard and screen-reader users start at its content.
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    mainRef.current?.focus()
  }, [location.pathname])

  return (
    <div className={styles['shell']}>
      <a className={styles['skipLink']} href="#main-content">
        Skip to main content
      </a>
      <Sidebar />
      <div className={styles['main']}>
        <MobileNavigation />
        <ServiceStatusBanner />
        <main id="main-content" ref={mainRef} tabIndex={-1} className={styles['mainRegion']}>
          <Suspense fallback={<LoadingState label="Loading" lines={3} block />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
