import { z } from 'zod'

/** The server session and its identity-bound antiforgery token. */
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

export const verificationSchema = z.object({
  verificationRequired: z.literal(true),
  challengeToken: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
  email: z.string(),
  expiresAtUtc: z.string().datetime({ offset: true }),
  resendAvailableAtUtc: z.string().datetime({ offset: true }),
})

export type EmailVerification = z.infer<typeof verificationSchema>
export const signInResultSchema = z.union([sessionSchema, verificationSchema])

export const SESSION_QUERY_KEY = ['auth', 'session'] as const

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'error'

export interface SignInCredentials {
  email: string
  password: string
}

export interface Registration extends SignInCredentials {
  displayName?: string | undefined
}
