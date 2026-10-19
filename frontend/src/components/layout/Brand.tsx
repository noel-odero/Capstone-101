import { Link } from 'react-router'
import { APP_NAME } from '@/domain/terminology'
import styles from './layout.module.css'

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#4256e8" />
      <circle cx="16" cy="16" r="7" fill="none" stroke="#fff" strokeWidth="3" />
      <circle cx="16" cy="16" r="2.5" fill="#fff" />
    </svg>
  )
}

export function Brand({ to = '/', className }: { to?: string; className?: string }) {
  return (
    <Link to={to} className={`${styles['brand']} ${className ?? ''}`} aria-label={`${APP_NAME}, home`}>
      <LogoMark />
      <span className={styles['brandName']}>{APP_NAME}</span>
    </Link>
  )
}
