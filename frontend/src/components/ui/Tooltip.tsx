import { Info } from 'lucide-react'
import { useId, useState, type KeyboardEvent, type ReactNode } from 'react'
import { cx } from './cx'
import styles from './ui.module.css'

export interface TooltipProps {
  /** Accessible name of the info button, for example "Definition of cumulative resistance burden". */
  label: string
  children: ReactNode
  align?: 'start' | 'end'
}

/**
 * An info button whose explanation opens on hover and keyboard focus and closes with Escape. Anything essential must
 * also appear in the page text: this only supplies extra definitions.
 */
export function Tooltip({ label, children, align = 'start' }: TooltipProps) {
  const id = useId()
  const [open, setOpen] = useState(false)

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <span
      className={styles['tooltip']}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={onKeyDown}
    >
      <button
        type="button"
        className={styles['tooltipTrigger']}
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((current) => !current)}
      >
        <Info size={15} aria-hidden="true" />
      </button>
      {open ? (
        <span role="tooltip" id={id} className={cx(styles['tooltipContent'], align === 'end' && styles['tooltipEnd'])}>
          {children}
        </span>
      ) : null}
    </span>
  )
}
