import type { HTMLAttributes } from 'react'
import { cx } from './cx'
import styles from './ui.module.css'

export type BadgeVariant = 'susceptible' | 'resistant' | 'warning' | 'unsupported' | 'info' | 'neutral'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

/** Status pill. Colour is only reinforcement: the children must always carry the meaning in words. */
export function Badge({ variant = 'neutral', className, ...rest }: BadgeProps) {
  return <span {...rest} className={cx(styles['badge'], styles[variant], className)} />
}
