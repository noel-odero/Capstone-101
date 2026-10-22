import { useQuery } from '@tanstack/react-query'
import { getSimulation } from '@/api/simulation-api'
import { queryKeys } from '@/api/query-keys'

/** A stored run never changes, so it is cached for the session. */
export function useSimulation(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.simulation(id ?? ''),
    queryFn: ({ signal }) => getSimulation(id ?? '', signal),
    enabled: id !== undefined,
    staleTime: Infinity,
  })
}
