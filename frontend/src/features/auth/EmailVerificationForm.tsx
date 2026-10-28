import { useEffect, useRef, useState, type FormEvent } from 'react'
import { normalizeError } from '@/api/api-errors'
import { Button } from '@/components/ui/Button'
import { useAuth } from './useAuth'
import styles from './auth.module.css'

export function EmailVerificationForm() {
  const auth = useAuth()
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<'verify' | 'resend' | null>(null)
  const [now, setNow] = useState(Date.now)
  const inFlight = useRef(false)
  const input = useRef<HTMLInputElement>(null)
  const pending = auth.verification

  useEffect(() => {
    input.current?.focus()
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  if (!pending) return null
  const resendIn = Math.max(0, Math.ceil((Date.parse(pending.resendAvailableAtUtc) - now) / 1000))
  const expired = Date.parse(pending.expiresAtUtc) <= now

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (inFlight.current) return
    if (!/^\d{6}$/.test(code)) {
      setError('Enter the six-digit code from your email.')
      input.current?.focus()
      return
    }
    inFlight.current = true
    setBusy('verify')
    setError(null)
    try {
      await auth.verifyEmail(code)
    } catch (cause) {
      const failure = normalizeError(cause)
      setError(
        failure.code === 'verification_code_expired'
          ? 'This code has expired. Request a new code.'
          : failure.code === 'invalid_verification_code'
            ? 'The code is incorrect or no longer valid. Check the latest email or request a new code.'
            : failure.message,
      )
      input.current?.focus()
    } finally {
      inFlight.current = false
      setBusy(null)
    }
  }

  const resend = async () => {
    if (inFlight.current) return
    inFlight.current = true
    setBusy('resend')
    setError(null)
    setNotice(null)
    try {
      await auth.resendVerification()
      setNow(Date.now())
      setCode('')
      setNotice('A new code has been sent. Check your inbox or spam folder.')
    } catch (cause) {
      setError(normalizeError(cause).message)
    } finally {
      inFlight.current = false
      setBusy(null)
    }
  }

  return (
    <form className={styles['form']} onSubmit={(event) => void submit(event)} noValidate>
      {error ? (
        <p className={styles['notice']} role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className={styles['hint']} role="status">
          {notice}
        </p>
      ) : null}
      <div className={styles['field']}>
        <label htmlFor="email-verification-code">Verification code</label>
        <input
          id="email-verification-code"
          ref={input}
          className={`${styles['input']} ${styles['codeInput']}`}
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
          aria-describedby="verification-hint"
          aria-invalid={error ? true : undefined}
        />
        <p id="verification-hint" className={styles['hint']}>
          {expired
            ? 'Code expired. Request a new one below.'
            : 'Valid for 10 minutes. Check your spam folder too.'}
        </p>
      </div>
      <Button type="submit" loading={busy === 'verify'} disabled={expired || busy === 'resend'}>
        Verify email
      </Button>
      <Button
        type="button"
        variant="secondary"
        loading={busy === 'resend'}
        disabled={resendIn > 0 || busy === 'verify'}
        onClick={() => void resend()}
      >
        {resendIn > 0 ? `Resend in ${resendIn}s` : 'Resend code'}
      </Button>
      <button
        className={styles['textButton']}
        type="button"
        disabled={busy !== null}
        onClick={auth.cancelVerification}
      >
        Back to email and password
      </button>
    </form>
  )
}
