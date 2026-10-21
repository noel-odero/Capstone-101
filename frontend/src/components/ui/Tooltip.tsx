import * as Primitive from '@radix-ui/react-tooltip'
import { FiInfo } from 'react-icons/fi'
import { useState, type ReactNode } from 'react'
import styles from './ui.module.css'

export interface TooltipProps {
  label: string
  children: ReactNode
  align?: 'start' | 'end'
}

/** Radix supplies focus, Escape, collision detection and portal positioning. */
export function Tooltip({ label, children, align = 'start' }: TooltipProps) {
  const [open, setOpen] = useState(false)
  return (
    <Primitive.Provider delayDuration={0}>
      <Primitive.Root open={open} onOpenChange={setOpen}>
        <Primitive.Trigger asChild>
          <button
            type="button"
            className={styles['tooltipTrigger']}
            aria-label={label}
            onClick={() => setOpen(true)}
          >
            <FiInfo size={15} aria-hidden="true" />
          </button>
        </Primitive.Trigger>
        <Primitive.Portal>
          <Primitive.Content
            sideOffset={6}
            align={align}
            collisionPadding={16}
            className={styles['tooltipContent']}
          >
            {children}
          </Primitive.Content>
        </Primitive.Portal>
      </Primitive.Root>
    </Primitive.Provider>
  )
}
