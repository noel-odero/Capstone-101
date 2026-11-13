import { UNAVAILABLE } from './metrics'

export interface AnalysisReference {
  id: string
  createdAtUtc: string
}

interface SampleReference {
  label: string
  runs: readonly AnalysisReference[]
}

export function buildAnalysisLabels(
  samples: readonly SampleReference[],
): ReadonlyMap<string, string> {
  return new Map(
    samples.flatMap((sample) =>
      [...sample.runs]
        .sort((a, b) => a.createdAtUtc.localeCompare(b.createdAtUtc) || a.id.localeCompare(b.id))
        .map((run, index) => [run.id, `${sample.label} · Analysis ${index + 1}`] as const),
    ),
  )
}

export function analysisLabel(
  run: AnalysisReference,
  labels: ReadonlyMap<string, string> = new Map(),
): string {
  const saved = labels.get(run.id)
  if (saved) return saved
  const date = new Date(run.createdAtUtc)
  if (Number.isNaN(date.getTime())) return `Analysis · ${UNAVAILABLE}`
  return `Analysis · ${new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)}`
}
