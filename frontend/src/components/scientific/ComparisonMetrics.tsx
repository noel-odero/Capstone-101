import { buildMetricRows, formatMetricValue } from '@/domain/metrics'
import { strategyResults } from '@/domain/runs'
import { strategyLabel } from '@/domain/terminology'
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
  const results = strategyResults(comparison)
  if (!results.length) return null
  return (
    <div className="stack">
      <div className={styles['tableWrap']}>
        <table className={styles['comparisonMetrics']}>
          <caption className="visually-hidden">Paired simulation metrics</caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {results.map((result) => (
                <th scope="col" key={result.strategy}>
                  {strategyLabel(result.strategy)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {buildMetricRows(results)
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
                  {row.values.map((value, index) => (
                    <td key={results[index]?.strategy}>{formatMetricValue(row.key, value)}</td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {!compact && results.some((result) => result.metrics.unsupportedStepCount > 0) ? (
        <p className={styles['coverageSummary']} role="note">
          Steps without applicable transitions leave the profile unchanged. They do not demonstrate
          effectiveness.
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
