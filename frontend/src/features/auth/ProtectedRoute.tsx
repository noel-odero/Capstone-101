import { Navigate, Outlet, useLocation } from 'react-router'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { useAuth } from './useAuth'

/**
 * Keeps signed-out visitors out of the workspace and remembers where they were going. This is a convenience only:
 * the API refuses every protected request without a valid session, whatever the browser shows.
 */
export function ProtectedRoute() {
  const auth = useAuth()
  const location = useLocation()

  if (auth.status === 'loading') {
    return (
      <div style={{ padding: 'var(--space-8)' }}>
        <LoadingState label="Checking your session" lines={2} />
      </div>
    )
  }
  if (auth.status === 'error') {
    return (
      <div style={{ padding: 'var(--space-8)' }}>
        <ErrorState error={auth.error} title="Your session could not be checked" onRetry={auth.retry} />
      </div>
    )
  }
  if (auth.status === 'anonymous') {
    if (auth.signedOutByUser) {
      return <Navigate to="/" replace />
    }
    const returnTo = `${location.pathname}${location.search}`
    return <Navigate to={`/auth/sign-in?returnTo=${encodeURIComponent(returnTo)}`} replace state={{ sessionExpired: auth.sessionExpired }} />
  }
  return <Outlet />
}
