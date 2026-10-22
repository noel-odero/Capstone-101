import { Link } from 'react-router'
import { APP_NAME } from '@/domain/terminology'
import styles from './layout.module.css'

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M24 23V13a9 9 0 0 0-18 0v9c0 6 8 7 11 2l4-7"
        fill="none"
        stroke="currentColor"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d="M23 25c-4 2-9-1-9-5 0-3 3-6 7-6"
        fill="none"
        stroke="#2263c7"
        strokeWidth="5"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function Brand({ to = '/', className }: { to?: string; className?: string }) {
  return (
    <Link
      to={to}
      className={`${styles['brand']} ${className ?? ''}`}
      aria-label={`${APP_NAME}, home`}
    >
      <LogoMark />
      <span className={styles['brandName']}>{APP_NAME}</span>
    </Link>
  )
}
