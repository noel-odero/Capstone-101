import { onUnauthenticated, setCsrfToken } from '@/api/http-client'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  getSession,
  register as registerRequest,
  signIn as signInRequest,
  signOut as signOutRequest,
} from './auth-api'
import { AuthContext, type AuthContextValue } from './auth-context'
import { SESSION_QUERY_KEY, type AuthStatus, type Session } from './auth-types'

/**
 * Session state for the whole application. The server owns the session (an HttpOnly cookie the script cannot read);
 * this provider only asks who the caller is, keeps the antiforgery token in memory, and reacts to expiry.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [sessionExpired, setSessionExpired] = useState(false)
  const [signedOutByUser, setSignedOutByUser] = useState(false)

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
    queryClient.removeQueries({ predicate: (candidate) => candidate.queryKey[0] !== 'auth' })
    setCsrfToken(session.csrfToken)
    setSessionExpired(false)
    setSignedOutByUser(false)
    queryClient.setQueryData<Session>(SESSION_QUERY_KEY, session)
  }

  const { mutateAsync: signInAsync } = useMutation({
    mutationFn: signInRequest,
    onSuccess: startSession,
  })
  const { mutateAsync: registerAsync } = useMutation({
    mutationFn: registerRequest,
    onSuccess: startSession,
  })

  const { mutateAsync: signOutAsync, isPending: signingOut } = useMutation({
    mutationFn: signOutRequest,
    onSuccess: async () => {
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
      signOutAsync,
      signingOut,
      query,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
