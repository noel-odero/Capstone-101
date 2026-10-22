import { z } from 'zod'
import { requestJson } from '@/api/http-client'
import { resistanceProfileSchema } from '@/domain/types'

export const sampleSchema = z.object({
  id: z.string().uuid(),
  label: z.string(),
  addedAtUtc: z.string(),
  resistanceProfile: resistanceProfileSchema,
  runs: z.array(z.object({ id: z.string().uuid(), createdAtUtc: z.string() })),
})
export type SavedSample = z.infer<typeof sampleSchema>
export const sampleKeys = {
  all: ['samples'] as const,
  detail: (id: string) => ['samples', id] as const,
}
export function listSamples(signal?: AbortSignal) {
  return requestJson('/samples', z.array(sampleSchema), { signal })
}
export function getSample(id: string, signal?: AbortSignal) {
  return requestJson(`/samples/${encodeURIComponent(id)}`, sampleSchema, { signal })
}
export function saveSample(request: { label: string; resistanceProfile: number[] }) {
  return requestJson('/samples', sampleSchema, { method: 'POST', body: request })
}
