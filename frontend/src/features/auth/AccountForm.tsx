import { FiEye as Eye, FiEyeOff as EyeOff, FiAlertTriangle as TriangleAlert } from 'react-icons/fi'
import { useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router'
import { normalizeError } from '@/api/api-errors'
import { Button } from '@/components/ui/Button'
import {
  firstInvalidField,
  fromServerFieldErrors,
  MAX_NAME_LENGTH,
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  validateAccount,
  type AccountErrors,
  type AccountField,
  type AccountMode,
} from './auth-validation'
import { useAuth } from './useAuth'
import styles from './auth.module.css'

interface FieldProps {
  id: string
  label: string
  error: string | undefined
  hint?: string
  optional?: boolean
  children: (describedBy: string | undefined) => ReactNode
}

function Field({ id, label, error, hint, optional = false, children }: FieldProps) {
  const describedBy =
    [error ? `${id}-error` : null, hint ? `${id}-hint` : null].filter(Boolean).join(' ') ||
    undefined
  return (
    <div className={styles['field']}>
      <label htmlFor={id}>
        {label}
        {optional ? <span className={styles['optional']}> (optional)</span> : null}
      </label>
      {children(describedBy)}
      {hint ? (
        <p id={`${id}-hint`} className={styles['hint']}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className={styles['fieldError']}>
          {error}
        </p>
      ) : null}
    </div>
  )
}

/** Email-and-password form for both signing in and creating an account. Submits once at a time and never retries by itself. */
export function AccountForm({ mode, switchTo }: { mode: AccountMode; switchTo: string }) {
  const auth = useAuth()
  const formId = useId()
  const inFlight = useRef(false)
  const refs = useRef<Partial<Record<AccountField, HTMLInputElement | null>>>({})
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<AccountErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const registering = mode === 'register'

  const focusFirst = (found: AccountErrors) => {
    const field = firstInvalidField(found)
    if (field) {
      refs.current[field]?.focus()
    }
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (inFlight.current) {
      return
    }
    const trimmedEmail = email.trim()
    const problems = validateAccount(mode, { email: trimmedEmail, password, displayName })
    setErrors(problems)
    setFormError(null)
    if (firstInvalidField(problems)) {
      focusFirst(problems)
      return
    }

    inFlight.current = true
    setSubmitting(true)
    try {
      if (registering) {
        await auth.register({ email: trimmedEmail, password, displayName })
      } else {
        await auth.signIn({ email: trimmedEmail, password })
      }
    } catch (error) {
      const failure = normalizeError(error)
      if (failure.isCancellation) {
        return
      }
      const fromServer = fromServerFieldErrors(failure.fieldErrors)
      if (failure.code === 'email_already_registered') {
        fromServer.email = failure.message
      }
      setErrors(fromServer)
      if (firstInvalidField(fromServer)) {
        focusFirst(fromServer)
      } else {
        setFormError(failure.message)
      }
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }

  const emailId = `${formId}-email`
  const passwordId = `${formId}-password`
  const nameId = `${formId}-name`

  return (
    <form className={styles['form']} onSubmit={(event) => void onSubmit(event)} noValidate>
      {formError ? (
        <p className={styles['notice']} role="alert">
          <TriangleAlert size={16} aria-hidden="true" /> {formError}
        </p>
      ) : null}

      {registering ? (
        <Field id={nameId} label="Name" optional error={errors.displayName}>
          {(describedBy) => (
            <input
              id={nameId}
              ref={(node) => {
                refs.current.displayName = node
              }}
              className={styles['input']}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              autoComplete="name"
              maxLength={MAX_NAME_LENGTH}
              aria-invalid={errors.displayName ? true : undefined}
              aria-describedby={describedBy}
            />
          )}
        </Field>
      ) : null}

      <Field id={emailId} label="Email" error={errors.email}>
        {(describedBy) => (
          <input
            id={emailId}
            ref={(node) => {
              refs.current.email = node
            }}
            className={styles['input']}
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete={registering ? 'email' : 'username'}
            autoCapitalize="none"
            spellCheck={false}
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={describedBy}
          />
        )}
      </Field>

      <Field
        id={passwordId}
        label="Password"
        error={errors.password}
        {...(registering ? { hint: `At least ${MIN_PASSWORD_LENGTH} characters.` } : {})}
      >
        {(describedBy) => (
          <div className={styles['passwordRow']}>
            <input
              id={passwordId}
              ref={(node) => {
                refs.current.password = node
              }}
              className={styles['input']}
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={registering ? 'new-password' : 'current-password'}
              maxLength={MAX_PASSWORD_LENGTH}
              aria-invalid={errors.password ? true : undefined}
              aria-describedby={describedBy}
            />
            <button
              type="button"
              className={styles['reveal']}
              onClick={() => setShowPassword((current) => !current)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
            >
              {showPassword ? (
                <EyeOff size={18} aria-hidden="true" />
              ) : (
                <Eye size={18} aria-hidden="true" />
              )}
            </button>
          </div>
        )}
      </Field>

      <Button type="submit" loading={submitting}>
        {registering ? 'Create account' : 'Sign in'}
      </Button>

      <p className={styles['switch']}>
        {registering ? 'Already have an account? ' : 'New here? '}
        <Link to={switchTo}>{registering ? 'Sign in' : 'Create an account'}</Link>
      </p>
    </form>
  )
}
