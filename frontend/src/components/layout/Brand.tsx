import { Link } from 'react-router'
import { APP_NAME } from '@/domain/terminology'
import styles from './layout.module.css'

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="15" cy="15" r="10" fill="none" stroke="#2f7bf5" strokeWidth="4.5" />
      <path d="M21.5 21.5 L27 27" stroke="#2f7bf5" strokeWidth="4.5" strokeLinecap="round" />
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
