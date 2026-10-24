import { Link } from 'react-router'
import { FiArrowUpRight, FiMoon, FiSun } from 'react-icons/fi'
import { REPOSITORY_URL } from '@/config/navigation'
import { APP_NAME } from '@/domain/terminology'
import { LogoMark } from '@/components/layout/Brand'
import { useAuth } from '@/features/auth/useAuth'
import styles from './landing.module.css'

function LandingBrand() {
  return (
    <Link to="/" className={styles['stewardBrand']} aria-label={`${APP_NAME} home`}>
      <LogoMark size={32} />
      <span>{APP_NAME}</span>
    </Link>
  )
}

export function LandingHeader({
  theme,
  onToggle,
}: {
  theme: 'dark' | 'light'
  onToggle: () => void
}) {
  const auth = useAuth()
  return (
    <header className={styles['landingHeader']}>
      <div className={styles['headerInner']}>
        <LandingBrand />
        <nav aria-label="Primary">
          <Link to="/documentation">Platform</Link>
          <Link to="/methodology">Research</Link>
        </nav>
        <div className={styles['headerActions']}>
          <nav className={styles.resourceLinks} aria-label="Research resources">
            <Link to="/methodology">Methodology</Link>
            <Link to="/limitations">Limitations</Link>
            <a href={REPOSITORY_URL} target="_blank" rel="noreferrer">
              Source <FiArrowUpRight aria-hidden="true" />
            </a>
          </nav>
          <button
            type="button"
            className={styles['themeButton']}
            onClick={onToggle}
            aria-label={`Switch landing page to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <FiSun /> : <FiMoon />}
          </button>
          <Link
            className={styles['signInLink']}
            to={auth.status === 'authenticated' ? '/app' : '/auth/sign-in'}
          >
            {auth.status === 'authenticated' ? 'Workspace' : 'Sign in'}
            <FiArrowUpRight />
          </Link>
        </div>
      </div>
    </header>
  )
}
