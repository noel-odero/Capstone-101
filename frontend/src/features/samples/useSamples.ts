import { useQuery } from '@tanstack/react-query'
import { getSample, listSamples, sampleKeys } from './sample-api'

export function useSamples() {
  return useQuery({ queryKey: sampleKeys.all, queryFn: ({ signal }) => listSamples(signal) })
}
export function useSample(id: string | null | undefined) {
  return useQuery({
    queryKey: sampleKeys.detail(id ?? ''),
    queryFn: ({ signal }) => getSample(id ?? '', signal),
    enabled: !!id,
  })
}
