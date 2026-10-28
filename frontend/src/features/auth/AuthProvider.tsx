import { onUnauthenticated, setCsrfToken } from '@/api/http-client'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  getSession,
  register as registerRequest,
  signIn as signInRequest,
  signOut as signOutRequest,
  verifyEmail as verifyEmailRequest,
  resendVerification as resendVerificationRequest,
} from './auth-api'
import { AuthContext, type AuthContextValue } from './auth-context'
import {
  SESSION_QUERY_KEY,
  verificationSchema,
  type AuthStatus,
  type EmailVerification,
  type Session,
} from './auth-types'

const VERIFICATION_KEY = 'stewardlab.email-verification'

function savedVerification(): EmailVerification | null {
  try {
    const parsed = verificationSchema.safeParse(
      JSON.parse(sessionStorage.getItem(VERIFICATION_KEY) ?? 'null'),
    )
    return parsed.success ? parsed.data : null
  } catch {
    return null
  }
}

function rememberVerification(value: EmailVerification | null) {
  try {
    if (value) sessionStorage.setItem(VERIFICATION_KEY, JSON.stringify(value))
    else sessionStorage.removeItem(VERIFICATION_KEY)
  } catch {
    // Verification still works in memory if this browser blocks session storage.
  }
}

/**
 * Session state for the whole application. The server owns the session (an HttpOnly cookie the script cannot read);
 * this provider only asks who the caller is, keeps the antiforgery token in memory, and reacts to expiry.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [sessionExpired, setSessionExpired] = useState(false)
  const [signedOutByUser, setSignedOutByUser] = useState(false)
  const [verification, setVerification] = useState<EmailVerification | null>(savedVerification)

  const updateVerification = (value: EmailVerification | null) => {
    rememberVerification(value)
    setVerification(value)
  }

  const query = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: async ({ signal }) => {
      const session = await getSession(signal)
      setCsrfToken(session.csrfToken)
      return session
    },
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: true,
  })

  useEffect(
    () =>
      onUnauthenticated(() => {
        const current = queryClient.getQueryData<Session>(SESSION_QUERY_KEY)
        if (current?.isAuthenticated) {
          setSessionExpired(true)
          setCsrfToken(null)
          queryClient.setQueryData<Session>(SESSION_QUERY_KEY, {
            ...current,
            isAuthenticated: false,
            user: null,
          })
        }
      }),
    [queryClient],
  )

  /** Whoever signs in next must not see what the previous person on this browser loaded. */
  const startSession = (session: Session) => {
    updateVerification(null)
    queryClient.removeQueries({ predicate: (candidate) => candidate.queryKey[0] !== 'auth' })
    setCsrfToken(session.csrfToken)
    setSessionExpired(false)
    setSignedOutByUser(false)
    queryClient.setQueryData<Session>(SESSION_QUERY_KEY, session)
  }

  const { mutateAsync: signInAsync } = useMutation({
    mutationFn: signInRequest,
    onSuccess: (result) => {
      if ('verificationRequired' in result) updateVerification(result)
      else startSession(result)
    },
  })
  const { mutateAsync: registerAsync } = useMutation({
    mutationFn: registerRequest,
    onSuccess: updateVerification,
  })

  const { mutateAsync: verifyAsync } = useMutation({
    mutationFn: ({ token, code }: { token: string; code: string }) =>
      verifyEmailRequest(token, code),
    onSuccess: startSession,
  })
  const { mutateAsync: resendAsync } = useMutation({
    mutationFn: resendVerificationRequest,
    onSuccess: updateVerification,
  })

  const { mutateAsync: signOutAsync, isPending: signingOut } = useMutation({
    mutationFn: signOutRequest,
    onSuccess: async () => {
      updateVerification(null)
      // The session reads as anonymous first, so the protected route leaves the workspace before any private query is dropped.
      setCsrfToken(null)
      setSessionExpired(false)
      setSignedOutByUser(true)
      queryClient.setQueryData<Session>(SESSION_QUERY_KEY, {
        isAuthenticated: false,
        user: null,
        csrfToken: '',
      })
      queryClient.removeQueries({ predicate: (candidate) => candidate.queryKey[0] !== 'auth' })
      await queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY })
    },
  })

  const session = query.data
  const status: AuthStatus = query.isPending
    ? 'loading'
    : query.isError
      ? 'error'
      : session?.isAuthenticated
        ? 'authenticated'
        : 'anonymous'

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session?.user ?? null,
      sessionExpired,
      signedOutByUser,
      signIn: async (credentials) => {
        await signInAsync(credentials)
      },
      register: async (registration) => {
        await registerAsync(registration)
      },
      verification,
      verifyEmail: async (code) => {
        if (!verification) throw new Error('Request an email code first.')
        await verifyAsync({ token: verification.challengeToken, code })
      },
      resendVerification: async () => {
        if (!verification) throw new Error('Request an email code first.')
        await resendAsync(verification.challengeToken)
      },
      cancelVerification: () => {
        rememberVerification(null)
        setVerification(null)
      },
      signOut: async () => {
        await signOutAsync()
      },
      signingOut,
      retry: () => void query.refetch(),
      error: query.error,
    }),
    [
      status,
      session,
      sessionExpired,
      signedOutByUser,
      signInAsync,
      registerAsync,
      verification,
      verifyAsync,
      resendAsync,
      signOutAsync,
      signingOut,
      query,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
