import { modelInfoSchema, type ModelInfo } from '@/domain/types'
import { requestJson } from './http-client'

export function getModelInfo(signal?: AbortSignal): Promise<ModelInfo> {
  return requestJson('/model', modelInfoSchema, { signal })
}
