import { z } from 'zod'
import { requestJson } from '@/api/http-client'
import { sessionSchema, type Registration, type Session, type SignInCredentials } from './auth-types'

/** Only same-site relative paths under the workspace may be the destination after signing in. */
export function safeReturnTo(value: string | null | undefined, fallback = '/app'): string {
  if (!value || value.length > 300 || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) {
    return fallback
  }
  return value.startsWith('/app') ? value : fallback
}

export function getSession(signal?: AbortSignal): Promise<Session> {
  return requestJson('/auth/session', sessionSchema, { signal })
}

/** Never retried automatically: a wrong password counts toward the account lockout. */
export function signIn(credentials: SignInCredentials): Promise<Session> {
  return requestJson('/auth/sign-in', sessionSchema, { method: 'POST', body: { email: credentials.email, password: credentials.password } })
}

export function register(registration: Registration): Promise<Session> {
  const name = registration.displayName?.trim()
  return requestJson('/auth/register', sessionSchema, {
    method: 'POST',
    body: { email: registration.email, password: registration.password, ...(name ? { displayName: name } : {}) },
  })
}

export function signOut(): Promise<undefined> {
  return requestJson('/auth/sign-out', z.undefined(), { method: 'POST' })
}
