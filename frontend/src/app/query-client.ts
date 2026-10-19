import { QueryClient } from '@tanstack/react-query'
import { isApiError } from '@/api/api-errors'

const MAX_READ_RETRIES = 2

/** Only reads that failed for a transient reason are retried. Mutations are never retried (see below). */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_READ_RETRIES && isApiError(error) && error.isTransient
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetryQuery,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
      // Creating a run stores it, and a timed-out request may already have been stored: never repeat it automatically.
      mutations: { retry: false },
    },
  })
}
