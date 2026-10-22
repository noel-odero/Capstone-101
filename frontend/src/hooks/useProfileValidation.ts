import { useQuery } from '@tanstack/react-query'
import { validateProfile } from '@/api/profile-api'
import { queryKeys } from '@/api/query-keys'
import type { ResistanceProfile } from '@/domain/types'

/**
 * One request per distinct profile, cached by its code: editing back to a profile already checked costs nothing,
 * and re-rendering never re-validates.
 */
export function useProfileValidation(profile: ResistanceProfile) {
  return useQuery({
    queryKey: queryKeys.profileValidation(profile),
    queryFn: ({ signal }) => validateProfile(profile, signal),
    staleTime: Infinity,
    gcTime: 10 * 60_000,
  })
}
