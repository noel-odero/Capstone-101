import { TriangleAlert } from 'lucide-react'
import { Link, Navigate, useLocation, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { LoadingState } from '@/components/ui/LoadingState'
import { LogoMark } from '@/components/layout/Brand'
import { AccountForm } from './AccountForm'
import { safeReturnTo } from './auth-api'
import type { AccountMode } from './auth-validation'
import { useAuth } from './useAuth'
import styles from './auth.module.css'

const COPY: Readonly<Record<AccountMode, { title: string; lead: string; switchPath: string }>> = {
  'sign-in': { title: 'Sign in', lead: 'Use your email and password.', switchPath: '/auth/register' },
  register: { title: 'Create an account', lead: 'Your simulations are saved to your account.', switchPath: '/auth/sign-in' },
}

/** The page around the form: redirects signed-in visitors on, and shows the session states. */
export function AuthPageShell({ mode }: { mode: AccountMode }) {
  const auth = useAuth()
  const location = useLocation()
  const [params] = useSearchParams()
  const returnParam = params.get('returnTo')
  const returnTo = safeReturnTo(returnParam)
  const state = location.state as { sessionExpired?: boolean } | null
  const expired = auth.sessionExpired || state?.sessionExpired === true
  const copy = COPY[mode]
  const switchTo = returnParam ? `${copy.switchPath}?returnTo=${encodeURIComponent(returnTo)}` : copy.switchPath

  if (auth.status === 'authenticated') {
    return <Navigate to={returnTo} replace />
  }

  return (
    <div className={styles['page']}>
      <Card className={styles['card']} aria-labelledby="account-title">
        <LogoMark size={44} />
        <h1 id="account-title">{copy.title}</h1>
        <p className="muted">{copy.lead}</p>

        {expired ? (
          <p className={styles['notice']} role="status">
            <TriangleAlert size={16} aria-hidden="true" /> Your session ended. Sign in again to continue.
          </p>
        ) : null}

        {auth.status === 'loading' ? <LoadingState label="Checking your session" lines={1} /> : null}
        {auth.status === 'error' ? (
          <div className="stack" role="alert">
            <p className={styles['notice']}>
              <TriangleAlert size={16} aria-hidden="true" /> The server could not be reached.
            </p>
            <Button variant="secondary" onClick={auth.retry}>
              Try again
            </Button>
          </div>
        ) : null}
        {auth.status === 'anonymous' ? <AccountForm mode={mode} switchTo={switchTo} /> : null}

        <p className={styles['hint']}>
          A research prototype, not a clinical tool. <Link to="/privacy">Privacy</Link>
        </p>
      </Card>
    </div>
  )
}
