import { z } from 'zod'

/** `GET /api/v1/auth/session` and the answer to sign-in and registration: who the browser is, and the antiforgery token it must send with state-changing requests. */
export const sessionSchema = z.object({
  isAuthenticated: z.boolean(),
  user: z
    .object({
      displayName: z.string(),
      email: z.string(),
    })
    .nullable(),
  csrfToken: z.string(),
})

export type Session = z.infer<typeof sessionSchema>
export type SessionUser = NonNullable<Session['user']>

export const SESSION_QUERY_KEY = ['auth', 'session'] as const

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'error'

export interface SignInCredentials {
  email: string
  password: string
}

export interface Registration extends SignInCredentials {
  displayName?: string | undefined
}
