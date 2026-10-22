import { simulationSchema, type Simulation } from '@/domain/types'
import { requestJson } from './http-client'

export function getSimulation(id: string, signal?: AbortSignal): Promise<Simulation> {
  return requestJson(`/simulations/${encodeURIComponent(id)}`, simulationSchema, { signal })
}
