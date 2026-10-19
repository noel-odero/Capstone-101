import { Outlet } from 'react-router'
import { AuthProvider } from '@/features/auth/AuthProvider'

/** Root route element: session state is available to every public and protected page below it. */
export function AuthRoot() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}
