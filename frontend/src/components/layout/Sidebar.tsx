import { FiLogOut as LogOut } from 'react-icons/fi'
import { NavLink, useLocation } from 'react-router'
import { workspaceNavigation } from '@/config/navigation'
import { useAuth } from '@/features/auth/useAuth'
import { Brand } from './Brand'
import { ThemeControl } from '@/components/ui/ThemeControl'
import { cx } from '@/components/ui/cx'
import styles from './layout.module.css'

export function WorkspaceNavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation()
  return (
    <nav aria-label="Workspace">
      <ul className={styles['navList']}>
        {workspaceNavigation.map(({ to, label, icon: Icon, end, alsoActiveFor }) => {
          const extra = alsoActiveFor?.some((path) => pathname.startsWith(path)) ?? false
          return (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={cx(styles['navLink'], extra && styles['navLinkActive'])}
                onClick={onNavigate}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{label}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

export function AccountFooter() {
  const { user, signOut, signingOut } = useAuth()
  const name = user?.displayName ?? 'Signed in'
  return (
    <div className={styles['sidebarFooter']}>
      <div className={styles['appearance']}>
        <span>Appearance</span>
        <ThemeControl />
      </div>
      <div className={styles['userCard']}>
        <span className={styles['avatar']} aria-hidden="true">
          {name.charAt(0).toUpperCase()}
        </span>
        <span className={styles['userText']}>
          <span className={styles['userName']}>{name}</span>
          <span className={styles['userEmail']}>{user?.email}</span>
        </span>
        <button
          type="button"
          className={styles['signOut']}
          onClick={() => void signOut()}
          disabled={signingOut}
          aria-label={signingOut ? 'Signing out' : 'Sign out'}
          title={signingOut ? 'Signing out' : 'Sign out'}
          aria-busy={signingOut || undefined}
        >
          <LogOut size={14} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

export function Sidebar() {
  return (
    <aside className={styles['sidebar']} aria-label="Workspace sidebar">
      <Brand to="/app" className={styles['brandOnDark']} />
      <WorkspaceNavLinks />
      <AccountFooter />
    </aside>
  )
}
