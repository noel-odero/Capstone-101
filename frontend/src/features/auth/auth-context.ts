import { createContext } from 'react'
import type { AuthStatus, Registration, SessionUser, SignInCredentials } from './auth-types'

export interface AuthContextValue {
  status: AuthStatus
  user: SessionUser | null
  /** True after the server rejected a request from a session that had been valid. */
  sessionExpired: boolean
  /** True after this user chose to sign out; the protected route then goes to the landing page, not to sign-in. */
  signedOutByUser: boolean
  /** Rejects with an `ApiError` when the credentials are wrong, the account is locked, or the server is unreachable. */
  signIn: (credentials: SignInCredentials) => Promise<void>
  /** Creates the account and signs it in. Rejects with an `ApiError` (409 when the email is already registered). */
  register: (registration: Registration) => Promise<void>
  signOut: () => Promise<void>
  signingOut: boolean
  retry: () => void
  error: unknown
}

export const AuthContext = createContext<AuthContextValue | null>(null)
