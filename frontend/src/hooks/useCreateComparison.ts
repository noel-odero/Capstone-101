import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createComparison } from '@/api/comparison-api'
import { queryKeys } from '@/api/query-keys'
import type { CreateComparisonRequest } from '@/domain/types'

/**
 * Creates and stores a paired run. It is never retried automatically. On success the stored comparison is cached
 * under its id, and history and sample lists are refreshed.
 */
export function useCreateComparison() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: CreateComparisonRequest) => createComparison(request),
    retry: false,
    onSuccess: (comparison) => {
      queryClient.setQueryData(queryKeys.comparison(comparison.id), comparison)
      void queryClient.invalidateQueries({ queryKey: queryKeys.recentRunsRoot })
      void queryClient.invalidateQueries({ queryKey: ['analysis-history'] })
      void queryClient.invalidateQueries({ queryKey: ['samples'] })
    },
  })
}
