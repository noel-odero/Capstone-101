import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import { cx } from './cx'
import styles from './ui.module.css'

type Variant = 'primary' | 'dark' | 'secondary' | 'ghost' | 'destructive'
type Size = 'md' | 'sm'

interface StyleProps {
  variant?: Variant
  size?: Size
  className?: string | undefined
}

export interface ButtonProps extends StyleProps, ButtonHTMLAttributes<HTMLButtonElement> {
  /** Shows a spinner and blocks activation while an action is running. */
  loading?: boolean
  children: ReactNode
}

function classes({ variant = 'primary', size = 'md', className }: StyleProps): string {
  return cx(styles['button'], styles[variant], size === 'sm' && styles['sm'], className)
}

export function Button({ variant, size, className, loading = false, disabled, children, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      className={classes({ variant, size, className })}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading ? <span className={styles['spinner']} aria-hidden="true" /> : null}
      {children}
    </button>
  )
}

export interface ButtonLinkProps extends StyleProps, LinkProps {}

/** A real link (not a clickable div) that looks like a button. */
export function ButtonLink({ variant, size, className, ...rest }: ButtonLinkProps) {
  return <Link {...rest} className={classes({ variant, size, className })} />
}
