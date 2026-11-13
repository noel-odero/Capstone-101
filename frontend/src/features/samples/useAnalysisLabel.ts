import { useMemo } from 'react'
import { analysisLabel, buildAnalysisLabels, type AnalysisReference } from '@/domain/analysis-label'
import { useSamples } from './useSamples'

export function useAnalysisLabel() {
  const samples = useSamples()
  const labels = useMemo(() => buildAnalysisLabels(samples.data ?? []), [samples.data])
  return (run: AnalysisReference) => analysisLabel(run, labels)
}
