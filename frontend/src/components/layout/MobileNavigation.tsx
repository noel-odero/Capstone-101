import { Menu, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'
import { Brand } from './Brand'
import { AccountFooter, WorkspaceNavLinks } from './Sidebar'
import styles from './layout.module.css'

/** Compact top bar with a modal drawer. The native dialog supplies focus trapping, Escape and focus return. */
export function MobileNavigation() {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const location = useLocation()

  useEffect(() => {
    dialogRef.current?.close()
  }, [location.pathname, location.search])

  const close = () => dialogRef.current?.close()

  return (
    <header className={styles['mobileBar']}>
      <Brand to="/app" />
      <button type="button" className={styles['menuButton']} onClick={() => dialogRef.current?.showModal()} aria-label="Open navigation menu">
        <Menu size={22} aria-hidden="true" />
      </button>
      <dialog
        ref={dialogRef}
        className={styles['drawer']}
        aria-label="Navigation menu"
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            close()
          }
        }}
      >
        <div className={styles['drawerHeader']}>
          <Brand to="/app" />
          <button type="button" className={styles['menuButton']} onClick={close} aria-label="Close navigation menu">
            <X size={22} aria-hidden="true" />
          </button>
        </div>
        <WorkspaceNavLinks onNavigate={close} />
        <AccountFooter />
      </dialog>
    </header>
  )
}
