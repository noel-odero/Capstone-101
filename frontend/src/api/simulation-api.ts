import { simulationSchema, type CreateSimulationRequest, type Simulation } from '@/domain/types'
import { requestJson } from './http-client'

/** Stores a new run on every call; callers must not retry it automatically. */
export function createSimulation(request: CreateSimulationRequest, signal?: AbortSignal): Promise<Simulation> {
  return requestJson('/simulations', simulationSchema, { method: 'POST', body: request, signal })
}

export function getSimulation(id: string, signal?: AbortSignal): Promise<Simulation> {
  return requestJson(`/simulations/${encodeURIComponent(id)}`, simulationSchema, { signal })
}
