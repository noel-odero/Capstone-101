import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { requestJson, TIMEOUTS } from '@/api/http-client'
import {
  experimentKindSchema,
  metricDefinitionsSchema,
  modelProvenanceSchema,
  recentRunsSchema,
  resistanceProfileSchema,
  seedConfigurationSchema,
  strategyResultSchema,
} from '@/domain/types'

export const SELECTION_LIMIT = 50
const idSchema = z
  .string()
  .uuid()
  .refine((id) => id !== '00000000-0000-0000-0000-000000000000')

export function readSelection(value: string | null): string[] {
  return [
    ...new Set(
      (value ?? '')
        .split(',')
        .filter((id) => idSchema.safeParse(id).success)
        .map((id) => id.toLowerCase()),
    ),
  ]
}

export function validSelection(value: string | null): boolean {
  const raw = (value ?? '').split(',')
  return (
    raw.length >= 2 &&
    raw.length <= SELECTION_LIMIT &&
    raw.every((id) => idSchema.safeParse(id).success) &&
    new Set(raw.map((id) => id.toLowerCase())).size === raw.length
  )
}

export const savedAnalysisSchema = z.object({
  id: z.string().uuid(),
  kind: experimentKindSchema,
  createdAtUtc: z.string(),
  initialProfile: resistanceProfileSchema,
  provenance: modelProvenanceSchema,
  seedConfiguration: seedConfigurationSchema,
  strategies: z.array(strategyResultSchema),
  metricDefinitions: metricDefinitionsSchema,
  comparisonVerified: z.boolean().nullable(),
  sampleId: z.string().uuid().nullable(),
})
export const historyComparisonSchema = z.object({
  analyses: z.array(savedAnalysisSchema),
  compatibility: z.object({
    status: z.enum(['compatible', 'exploratory', 'incompatible']),
    issues: z.array(
      z.object({
        code: z.string(),
        severity: z.string(),
        message: z.string(),
        analysisIds: z.array(z.string().uuid()),
      }),
    ),
  }),
  burdenDifferences: z.array(
    z.object({
      analysisId: z.string().uuid(),
      ppoMinusDqn: z.number().nullable(),
      ppoMinusBaseline: z.number().nullable(),
      dqnMinusBaseline: z.number().nullable(),
    }),
  ),
  interpretation: z.string(),
})
export type SavedAnalysis = z.infer<typeof savedAnalysisSchema>
export type HistoryComparison = z.infer<typeof historyComparisonSchema>

export function historyQuery(params: URLSearchParams) {
  const requested = Number(params.get('page'))
  return {
    page: Number.isInteger(requested) && requested >= 1 ? requested : 1,
    pageSize: 10,
    profile: params.get('profile') || undefined,
    initialResistantCount: params.get('initialResistantCount') || undefined,
    strategy: params.get('strategy') || undefined,
    from: params.get('from') ? `${params.get('from')}T00:00:00.000Z` : undefined,
    to: params.get('to') ? `${params.get('to')}T23:59:59.999Z` : undefined,
    sort: params.get('sort') || 'newest',
  }
}

export function useAnalysisHistory(params: URLSearchParams) {
  const query = historyQuery(params)
  return useQuery({
    queryKey: ['analysis-history', query],
    queryFn: ({ signal }) => requestJson('/analyses', recentRunsSchema, { query, signal }),
    staleTime: 15_000,
    placeholderData: keepPreviousData,
  })
}

export function useHistoryComparison(ids: string[], enabled: boolean) {
  return useQuery({
    queryKey: ['history-comparison', ids],
    queryFn: ({ signal }) =>
      requestJson('/analyses/compare', historyComparisonSchema, {
        method: 'POST',
        body: { analysisIds: ids },
        signal,
        timeoutMs: TIMEOUTS.read,
      }),
    enabled,
    staleTime: Infinity,
    retry: false,
  })
}

export const collectionSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  question: z.string().nullable(),
  createdAtUtc: z.string(),
  analysisIds: z.array(z.string().uuid()),
})
export type AnalysisCollection = z.infer<typeof collectionSchema>

export function useAnalysisCollections() {
  return useQuery({
    queryKey: ['analysis-collections'],
    queryFn: ({ signal }) =>
      requestJson('/analysis-collections', z.array(collectionSchema), { signal }),
  })
}

export function useSaveCollection() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; question?: string; analysisIds: string[] }) =>
      requestJson('/analysis-collections', collectionSchema, { method: 'POST', body }),
    retry: false,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['analysis-collections'] })
    },
  })
}
