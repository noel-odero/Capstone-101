import { useQuery } from '@tanstack/react-query'
import { getModelInfo } from '@/api/model-api'
import { queryKeys } from '@/api/query-keys'

export function useModelMetadata() {
  return useQuery({
    queryKey: queryKeys.model,
    queryFn: ({ signal }) => getModelInfo(signal),
    staleTime: 5 * 60_000,
  })
}
