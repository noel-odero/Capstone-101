import { Link } from 'react-router'
import { FiArrowUpRight, FiMoon, FiSun } from 'react-icons/fi'
import { REPOSITORY_URL } from '@/config/navigation'
import { useAuth } from '@/features/auth/useAuth'
import styles from './landing.module.css'

export function StewardBrand() {
  return (
    <Link to="/" className={styles['stewardBrand']} aria-label="StewardLab home">
      <svg viewBox="0 0 32 36" width="30" height="34" fill="none" aria-hidden="true">
        <path d="M16 1 30 9v18l-14 8L2 27V9Z" stroke="currentColor" strokeWidth="1.3" />
        <path d="m16 6 10 6v12l-10 6-10-6V12Z" stroke="currentColor" />
        <path d="m16 11 6 4v7l-6 4-6-4v-7Z" stroke="currentColor" />
        <path d="M16 1v34M2 9l28 18M30 9 2 27" stroke="currentColor" strokeOpacity=".5" />
      </svg>
      <span>
        StewardLab<span className={styles['brandPoint']}>.</span>
      </span>
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
        <StewardBrand />
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
            {auth.status === 'authenticated' ? 'Workbench' : 'Sign in'}
            <FiArrowUpRight />
          </Link>
        </div>
      </div>
    </header>
  )
}
