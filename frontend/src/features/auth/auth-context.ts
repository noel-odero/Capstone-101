import { createContext } from 'react'
import type {
  AuthStatus,
  EmailVerification,
  Registration,
  SessionUser,
  SignInCredentials,
} from './auth-types'

export interface AuthContextValue {
  status: AuthStatus
  user: SessionUser | null
  /** True after the server rejected a request from a session that had been valid. */
  sessionExpired: boolean
  /** True after this user chose to sign out; the protected route then goes to the landing page, not to sign-in. */
  signedOutByUser: boolean
  /** Rejects with an `ApiError` when the credentials are wrong, the account is locked, or the server is unreachable. */
  signIn: (credentials: SignInCredentials) => Promise<void>
  /** Requests an email code; registration does not start an authenticated session. */
  register: (registration: Registration) => Promise<void>
  verification: EmailVerification | null
  verifyEmail: (code: string) => Promise<void>
  resendVerification: () => Promise<void>
  cancelVerification: () => void
  signOut: () => Promise<void>
  signingOut: boolean
  retry: () => void
  error: unknown
}

export const AuthContext = createContext<AuthContextValue | null>(null)
