import { buildMetricRows, formatMetricValue } from '@/domain/metrics'
import type { Comparison } from '@/domain/types'
import { Tooltip } from '@/components/ui/Tooltip'
import styles from './scientific.module.css'

export function ComparisonMetrics({
  comparison,
  compact = false,
}: {
  comparison: Comparison
  compact?: boolean
}) {
  const { ppo, baseline } = comparison
  if (!ppo || !baseline) return null
  return (
    <div className="stack">
      <div className={styles['tableWrap']}>
        <table className={styles['comparisonMetrics']}>
          <caption className="visually-hidden">Paired simulation metrics</caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">PPO</th>
              <th scope="col">Random baseline</th>
            </tr>
          </thead>
          <tbody>
            {buildMetricRows(ppo.metrics, baseline.metrics)
              .filter(
                (row) =>
                  !compact ||
                  [
                    'cumulativeResistanceBurden',
                    'resistanceEmergenceEvents',
                    'finalSusceptibleCount',
                  ].includes(row.key),
              )
              .map((row) => (
                <tr key={row.key}>
                  <th scope="row">
                    {row.label}{' '}
                    <Tooltip label={`Definition of ${row.label}`}>
                      {comparison.metricDefinitions[row.key]?.definition ??
                        'Definition not provided.'}
                    </Tooltip>
                  </th>
                  <td>{formatMetricValue(row.key, row.ppo)}</td>
                  <td>{formatMetricValue(row.key, row.baseline)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {!compact && ppo.metrics.unsupportedStepCount + baseline.metrics.unsupportedStepCount > 0 ? (
        <p className={styles['coverageSummary']} role="note">
          No candidate transition data for {ppo.metrics.unsupportedStepCount} of {ppo.steps.length}{' '}
          PPO steps and {baseline.metrics.unsupportedStepCount} of {baseline.steps.length} baseline
          steps. Unchanged profiles on these steps are a data gap, not evidence of effectiveness.
        </p>
      ) : null}
      {!compact ? (
        <p className="muted" style={{ fontSize: 'var(--text-xs)' }}>
          {comparison.singleRunCaveat}
        </p>
      ) : null}
    </div>
  )
}
