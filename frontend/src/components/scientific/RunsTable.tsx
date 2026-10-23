import { Link } from 'react-router'
import { Button } from '@/components/ui/Button'
import { formatDateTime, shortId } from '@/domain/formatters'
import { profileToCode } from '@/domain/profile'
import { runDetailPath } from '@/domain/runs'
import { STRATEGY_NAMES } from '@/domain/terminology'
import type { RecentRuns, RunSummary, StrategyId } from '@/domain/types'
import { formatMetricValue } from '@/domain/metrics'
import styles from './runs-table.module.css'

function burdenOf(run: RunSummary, strategy: StrategyId): string {
  const found = run.strategies.find((candidate) => candidate.strategy === strategy)
  return found
    ? formatMetricValue('cumulativeResistanceBurden', found.cumulativeResistanceBurden)
    : '\u2014'
}

export interface RunsTableProps {
  runs: readonly RunSummary[]
  caption: string
  sampleLabels?: ReadonlyMap<string, string>
}

/** Stored runs: when, from which profile, the resistance burden of each strategy, and a link to open it. */
export function RunsTable({ runs, caption, sampleLabels }: RunsTableProps) {
  return (
    <div className={styles['wrap']}>
      <table className={styles['table']}>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Run</th>
            <th scope="col">Date</th>
            <th scope="col">Initial profile</th>
            <th scope="col">
              <span className={styles['dotPpo']} aria-hidden="true" />
              {STRATEGY_NAMES.ppo} burden
            </th>
            <th scope="col">
              <span className={styles['dotDqn']} aria-hidden="true" />
              DQN burden
            </th>
            <th scope="col">
              <span className={styles['dotBaseline']} aria-hidden="true" />
              Baseline burden
            </th>
            <th scope="col">
              <span className="visually-hidden">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const path = runDetailPath(run)
            return (
              <tr key={run.id}>
                <th scope="row" title={run.id}>
                  {sampleLabels?.get(run.id) ??
                    (run.kind === 'comparison' ? 'Comparison' : 'Simulation')}{' '}
                  <span className="muted">{shortId(run.id)}</span>
                </th>
                <td>{formatDateTime(run.createdAtUtc)}</td>
                <td className={styles['code']}>{profileToCode(run.initialProfile)}</td>
                <td className="tabular">{burdenOf(run, 'ppo')}</td>
                <td className="tabular">{burdenOf(run, 'dqn')}</td>
                <td className="tabular">{burdenOf(run, 'random_susceptible_baseline')}</td>
                <td>
                  {path ? <Link to={path}>Open</Link> : <span className="muted">No view</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export interface PagerProps {
  data: Pick<RecentRuns, 'page' | 'pageSize' | 'totalCount'>
  onPage: (page: number) => void
}

export function Pager({ data, onPage }: PagerProps) {
  const pages = Math.max(1, Math.ceil(data.totalCount / data.pageSize))
  return (
    <div className={styles['pager']}>
      <span>
        Page {data.page} of {pages} &middot; {data.totalCount} runs
      </span>
      <span className="row">
        <Button
          variant="secondary"
          size="sm"
          disabled={data.page <= 1}
          onClick={() => onPage(data.page - 1)}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={data.page >= pages}
          onClick={() => onPage(data.page + 1)}
        >
          Next
        </Button>
      </span>
    </div>
  )
}
