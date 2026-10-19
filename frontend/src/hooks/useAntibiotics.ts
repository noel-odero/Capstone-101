import { useQuery } from '@tanstack/react-query'
import { getAntibiotics } from '@/api/profile-api'
import { queryKeys } from '@/api/query-keys'
import { buildCatalogue } from '@/domain/antibiotics'

/** The seven antibiotics in profile order, checked against their action ids; fixed for the frozen model. */
export function useAntibiotics() {
  return useQuery({
    queryKey: queryKeys.antibiotics,
    queryFn: ({ signal }) => getAntibiotics(signal),
    select: buildCatalogue,
    staleTime: Infinity,
  })
}
