import { FiMenu as Menu, FiX as X } from 'react-icons/fi'
import { useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router'
import { ButtonLink } from '@/components/ui/Button'
import { ThemeControl } from '@/components/ui/ThemeControl'
import { publicNavigation, SIGN_IN_PATH, WORKSPACE_PATH } from '@/config/navigation'
import { useAuth } from '@/features/auth/useAuth'
import { Brand } from './Brand'
import { ContentContainer } from './ContentContainer'
import styles from './layout.module.css'

export function PublicHeader({ appearance }: { appearance?: ReactNode } = {}) {
  const auth = useAuth()
  const location = useLocation()
  // The menu is remembered with the page it was opened on, so navigating closes it without an effect.
  const [openOn, setOpenOn] = useState<string | null>(null)
  const open = openOn === location.pathname

  const account =
    auth.status === 'authenticated' ? (
      <ButtonLink to={WORKSPACE_PATH} size="sm">
        Open workspace
      </ButtonLink>
    ) : (
      <ButtonLink to={SIGN_IN_PATH} size="sm">
        Sign in
      </ButtonLink>
    )

  return (
    <header className={styles['publicHeader']}>
      <ContentContainer>
        <div className={styles['publicHeaderInner']}>
          <Brand className={styles['publicBrand']} />
          <nav className={styles['publicNav']} aria-label="Primary">
            {publicNavigation.map((link) => (
              <NavLink key={link.to} to={link.to} className={styles['publicNavLink']}>
                {link.label}
              </NavLink>
            ))}
          </nav>
          <div className={styles['publicActions']}>
            {appearance ?? <ThemeControl />}
            {account}
            <button
              type="button"
              className={styles['publicMenuButton']}
              aria-expanded={open}
              aria-controls="public-mobile-nav"
              aria-label={open ? 'Close menu' : 'Open menu'}
              onClick={() => setOpenOn(open ? null : location.pathname)}
            >
              {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
            </button>
          </div>
        </div>
      </ContentContainer>
      {open ? (
        <nav
          id="public-mobile-nav"
          className={styles['publicMobileNav']}
          aria-label="Primary (mobile)"
        >
          {publicNavigation.map((link) => (
            <NavLink key={link.to} to={link.to} className={styles['publicNavLink']}>
              {link.label}
            </NavLink>
          ))}
        </nav>
      ) : null}
    </header>
  )
}
