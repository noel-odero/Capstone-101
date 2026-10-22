import type { ResistanceProfile } from '@/domain/types'
import { profileToCode } from '@/domain/profile'

/** Every query key in one place so invalidation targets exactly what a mutation changes. */
export const queryKeys = {
  health: ['health'] as const,
  model: ['model'] as const,
  antibiotics: ['antibiotics'] as const,
  profileValidation: (profile: ResistanceProfile) => ['profile-validation', profileToCode(profile)] as const,
  simulation: (id: string) => ['simulation', id] as const,
  comparison: (id: string) => ['comparison', id] as const,
  recommendation: (simulationId: string) => ['recommendation', simulationId] as const,
  recentRunsRoot: ['recent-runs'] as const,
  recentRuns: (page: number, pageSize: number) => ['recent-runs', page, pageSize] as const,
}
