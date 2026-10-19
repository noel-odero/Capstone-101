import { Disclosure } from '@/components/ui/Disclosure'
import { MetricCard } from '@/components/ui/MetricCard'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import {
  METRIC_LABELS,
  formatMetricValue,
  metricDefinitionFor,
  type MetricKey,
} from '@/domain/metrics'
import { GLOSSARY, terminationLabel } from '@/domain/terminology'
import type { MetricDefinitions, StrategyMetrics, StrategyResult } from '@/domain/types'
import styles from './scientific.module.css'

const HEADLINE_METRICS = [
  'cumulativeResistanceBurden',
  'resistanceEmergenceEvents',
  'finalResistantCount',
  'finalSusceptibleCount',
  'unsupportedStepCount',
] as const satisfies readonly MetricKey[]

export interface OutcomeSummaryProps {
  result: StrategyResult
  definitions: MetricDefinitions
}

/** Headline metrics for one strategy. Each card carries the server's unit text and definition. */
export function OutcomeSummary({ result, definitions }: OutcomeSummaryProps) {
  return (
    <div className="stack">
      <div className={styles['metricGrid']}>
        {HEADLINE_METRICS.map((key) => {
          const definition = metricDefinitionFor(definitions, key)
          return (
            <MetricCard
              key={key}
              label={METRIC_LABELS[key]}
              value={formatMetricValue(key, result.metrics[key])}
              caption={definition?.unit}
              definition={definition?.definition}
            />
          )
        })}
      </div>
      <p>
        <StatusIndicator kind="info" label="Termination" />{' '}
        <span>{terminationLabel(result.terminationReason)}</span>
      </p>
      <Disclosure summary="All metric definitions (verbatim from the simulator)">
        <MetricDefinitionsTable definitions={definitions} columns={[{ label: result.displayLabel, metrics: result.metrics }]} />
      </Disclosure>
    </div>
  )
}

export interface MetricDefinitionsTableProps {
  definitions: MetricDefinitions
  columns: ReadonlyArray<{ label: string; metrics: StrategyMetrics }>
}

/** Every metric the run returned, its values, and the server's kind, unit, aggregation and definition text. */
export function MetricDefinitionsTable({ definitions, columns }: MetricDefinitionsTableProps) {
  const keys = (Object.keys(METRIC_LABELS) as MetricKey[]).filter((key) => definitions[key] !== undefined)
  return (
    <div className={styles['tableWrap']}>
      <table className={styles['definitionsTable']}>
        <caption className="visually-hidden">Metric definitions</caption>
        <thead>
          <tr>
            <th scope="col">Metric</th>
            {columns.map((column) => (
              <th scope="col" key={column.label}>
                {column.label}
              </th>
            ))}
            <th scope="col">Definition, unit and aggregation</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const definition = definitions[key]
            return (
              <tr key={key}>
                <th scope="row">{METRIC_LABELS[key]}</th>
                {columns.map((column) => (
                  <td key={column.label}>{formatMetricValue(key, column.metrics[key])}</td>
                ))}
                <td className={styles['definitionText']}>
                  {definition?.definition}
                  <br />
                  <em>
                    {definition?.kind}; {definition?.unit}. {definition?.aggregation}
                  </em>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="muted" style={{ padding: 'var(--space-3)' }}>
        {GLOSSARY.resistanceEmergence}
      </p>
    </div>
  )
}
