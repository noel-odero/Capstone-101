import { useQuery } from '@tanstack/react-query'
import { getRecommendation } from '@/api/recommendation-api'
import { queryKeys } from '@/api/query-keys'

export function useRecommendation(simulationId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.recommendation(simulationId ?? ''),
    queryFn: ({ signal }) => getRecommendation(simulationId ?? '', signal),
    enabled: simulationId !== undefined,
    staleTime: Infinity,
  })
}
