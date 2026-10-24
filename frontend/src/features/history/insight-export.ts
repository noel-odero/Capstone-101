import { strategyLabel } from '@/domain/terminology'
import type { HistoryComparison } from './history-api'

export function metricsCsv(data: HistoryComparison): string {
  const cell = (value: string | number | null) => {
    if (value == null) return ''
    const text =
      typeof value === 'string' && /^[=+@\-\t\r]/.test(value) ? `'${value}` : String(value)
    return `"${text.replaceAll('"', '""')}"`
  }
  const rows: (string | number | null)[][] = [
    [
      'analysis_id',
      'created_at_utc',
      'initial_profile',
      'strategy',
      'burden',
      'emergence_events',
      'remaining_options',
      'unsupported_steps',
      'recorded_steps',
      'model_id',
      'checkpoint_sha256',
      'dataset_sha256',
      'scenario',
      'horizon',
      'environment_seed',
      'policy_seed',
      'shared_conditions_verified',
    ],
  ]
  for (const run of data.analyses)
    for (const result of run.strategies)
      rows.push([
        run.id,
        run.createdAtUtc,
        run.initialProfile.join(''),
        result.strategy,
        result.metrics.cumulativeResistanceBurden,
        result.metrics.resistanceEmergenceEvents,
        result.metrics.finalSusceptibleCount,
        result.metrics.unsupportedStepCount,
        result.metrics.treatmentSteps,
        result.model?.modelId ??
          (result.strategy === 'ppo' && run.provenance.algorithm === 'MaskablePPO'
            ? run.provenance.modelId
            : null),
        result.model?.checkpointSha256 ??
          (result.strategy === 'ppo' && run.provenance.algorithm === 'MaskablePPO'
            ? run.provenance.checkpointSha256
            : null),
        run.provenance.interactionDataSha256,
        run.provenance.scenarioId,
        run.provenance.horizon,
        result.environmentSeed,
        result.policySeed,
        String(run.comparisonVerified),
      ])
  return rows.map((row) => row.map(cell).join(',')).join('\r\n')
}

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export function evidenceReport(
  data: HistoryComparison,
  title = 'Analysis Insights',
  question = '',
): string {
  const text = escapeHtml
  const table = (headings: string[], rows: unknown[][]) =>
    `<table><thead><tr>${headings.map((heading) => `<th>${text(heading)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${text(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table>`
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${text(title)} · AMR Decision Support</title>
<style>body{font:14px/1.6 system-ui;color:#222;max-width:1100px;margin:48px auto;padding:0 24px}h1,h2{letter-spacing:-.03em}h2{margin-top:40px}p,li{max-width:95ch}table{border-collapse:collapse;width:100%;font-size:12px;margin:16px 0}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd;overflow-wrap:anywhere}th{background:#f5f5f5}code,pre{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}small{color:#666}@media print{body{margin:0}section{break-inside:avoid}details>div{display:block}}</style>
<body><small>AMR DECISION SUPPORT / RESEARCH EVIDENCE</small><h1>${text(title)}</h1>${question ? `<p><strong>Research question:</strong> ${text(question)}</p>` : ''}
<p>${data.analyses.length} selected analyses · Exported ${text(new Date().toISOString())}</p><p>${text(data.interpretation)}</p>
<h2>Comparison limits</h2><p>Status: ${text(data.compatibility.status)}</p><ul>${data.compatibility.issues.map((issue) => `<li>${text(issue.message)} (${text(issue.analysisIds.join(', '))})</li>`).join('')}</ul>
${data.analyses
  .map(
    (
      run,
    ) => `<section><h2>Profile ${text(run.initialProfile.join(''))}</h2><p>${text(run.id)} · ${text(run.createdAtUtc)}</p>
${table(
  ['Policy', 'Burden', 'Emergence', 'Remaining options', 'Unsupported steps', 'Recorded steps'],
  run.strategies.map((result) => [
    strategyLabel(result.strategy),
    result.metrics.cumulativeResistanceBurden,
    result.metrics.resistanceEmergenceEvents,
    result.metrics.finalSusceptibleCount,
    result.metrics.unsupportedStepCount,
    result.metrics.treatmentSteps,
  ]),
)}
${run.strategies
  .map(
    (result) =>
      `<h3>${text(strategyLabel(result.strategy))} · recorded sequence and transitions</h3>${table(
        [
          'Step',
          'Selected antibiotic',
          'Outcome',
          'Target',
          'Profile after',
          'Source IDs',
          'Transition data',
        ],
        result.steps.map((step) => [
          step.treatmentStepAfter,
          step.antibiotic,
          step.selectedOutcome ?? 'No change',
          step.selectedTargetDrug ?? '—',
          step.resistanceProfileAfter.join(''),
          step.sourceIds.join(', '),
          step.hasCandidateTransition ? 'Available' : 'No applicable data',
        ]),
      )}`,
  )
  .join('')}
<details><summary>Stored configuration, checkpoint identities and metric definitions</summary><div><pre>${text(JSON.stringify({ provenance: run.provenance, seeds: run.seedConfiguration, sharedConditionsVerified: run.comparisonVerified, policyModels: run.strategies.map((result) => ({ strategy: result.strategy, model: result.model ?? null })), metricDefinitions: run.metricDefinitions }, null, 2))}</pre></div></details></section>`,
  )
  .join('')}
<p><strong>Research prototype.</strong> Model-derived findings, not clinical treatment recommendations. Unsupported steps represent evidence gaps. Scenario probabilities are not empirical clinical probabilities.</p></body></html>`
}

export function downloadEvidence(contents: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([contents], { type }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
