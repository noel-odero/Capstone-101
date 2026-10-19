import { Tooltip } from '@/components/ui/Tooltip'
import { TransitionSupportNotice } from '@/components/scientific/TransitionSupportNotice'
import { buildMetricRows, formatMetricValue, metricDefinitionFor } from '@/domain/metrics'
import { STRATEGY_NAMES, terminationLabel } from '@/domain/terminology'
import type { MetricDefinitions, StrategyResult } from '@/domain/types'
import styles from './simulation.module.css'

export interface KeyMetricsTableProps {
  ppo: StrategyResult
  baseline: StrategyResult
  definitions: MetricDefinitions
}

/** Returned metrics side by side, with the server's definition one press away. Nothing is derived or ranked here. */
export function KeyMetricsTable({ ppo, baseline, definitions }: KeyMetricsTableProps) {
  const rows = buildMetricRows(ppo.metrics, baseline.metrics)
  const unsupported = [
    { strategyName: STRATEGY_NAMES.ppo, result: ppo },
    { strategyName: STRATEGY_NAMES.random_susceptible_baseline, result: baseline },
  ]
    .filter(({ result }) => result.metrics.unsupportedStepCount > 0)
    .map(({ strategyName, result }) => ({ strategyName, count: result.metrics.unsupportedStepCount, total: result.metrics.treatmentSteps }))

  return (
    <div className="stack">
      <div className="scroll-x">
        <table className={styles['metricsTable']}>
          <caption className="visually-hidden">Key metrics for each strategy</caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">PPO</th>
              <th scope="col">Baseline</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const definition = metricDefinitionFor(definitions, row.key)
              return (
                <tr key={row.key}>
                  <th scope="row">
                    <span className="row" style={{ gap: '0.25rem', flexWrap: 'nowrap' }}>
                      {row.label}
                      {definition ? <Tooltip label={`Definition of ${row.label}`}>{definition.definition}</Tooltip> : null}
                    </span>
                  </th>
                  <td>{formatMetricValue(row.key, row.ppo)}</td>
                  <td>{formatMetricValue(row.key, row.baseline)}</td>
                </tr>
              )
            })}
            <tr>
              <th scope="row">Ended</th>
              <td style={{ fontSize: 'var(--text-xs)' }}>{terminationLabel(ppo.terminationReason)}</td>
              <td style={{ fontSize: 'var(--text-xs)' }}>{terminationLabel(baseline.terminationReason)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {unsupported.length > 0 ? <TransitionSupportNotice summaries={unsupported} /> : null}
    </div>
  )
}
