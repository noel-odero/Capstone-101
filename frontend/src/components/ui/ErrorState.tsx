import { FiAlertCircle as CircleAlert } from 'react-icons/fi'
import type { ReactNode } from 'react'
import { errorTitle, normalizeError } from '@/api/api-errors'
import { Button } from './Button'
import { cx } from './cx'
import styles from './ui.module.css'

export interface ErrorStateProps {
  error: unknown
  /** Heading override; defaults to a title derived from the error kind. */
  title?: string
  /** Offered only when repeating the action is safe (reads and validation, never run creation). */
  onRetry?: () => void
  retryLabel?: string
  children?: ReactNode
}

export function ErrorState({
  error,
  title,
  onRetry,
  retryLabel = 'Try again',
  children,
}: ErrorStateProps) {
  const apiError = normalizeError(error)
  const fieldErrors = Object.entries(apiError.fieldErrors)

  return (
    <div className={cx(styles['state'], styles['error'])} role="alert">
      <span className={styles['stateIcon']} aria-hidden="true">
        <CircleAlert size={20} />
      </span>
      <h3>{title ?? errorTitle(apiError)}</h3>
      <p className={styles['stateDescription']}>{apiError.message}</p>
      {fieldErrors.length > 0 ? (
        <ul className={styles['fieldErrors']}>
          {fieldErrors.flatMap(([field, messages]) =>
            messages.map((message) => (
              <li key={`${field}:${message}`}>
                <strong>{field}:</strong> {message}
              </li>
            )),
          )}
        </ul>
      ) : null}
      {children}
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
      {apiError.correlationId || apiError.code ? (
        <ul className={styles['errorMeta']}>
          {apiError.code ? <li>Error code: {apiError.code}</li> : null}
          {apiError.correlationId ? <li>Correlation ID: {apiError.correlationId}</li> : null}
        </ul>
      ) : null}
    </div>
  )
}
