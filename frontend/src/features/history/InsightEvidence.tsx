import { Button } from '@/components/ui/Button'
import { formatDateTime, shortId } from '@/domain/formatters'
import { STRATEGY_COLORS, strategyLabel } from '@/domain/terminology'
import type { SavedAnalysis } from './history-api'
import { ProfileIndicators } from './ProfileIndicators'
import {
  INSIGHT_POLICIES,
  INVESTIGATION_LABELS,
  matchesInvestigation,
  policyResult,
  type Investigation,
} from './insight-data'
import styles from './insights.module.css'

export function InsightEvidence({
  records,
  filter,
  profile,
  onFilter,
  onProfile,
  onInspect,
}: {
  records: SavedAnalysis[]
  filter: Investigation
  profile: string
  onFilter: (filter: Investigation) => void
  onProfile: (profile: string) => void
  onInspect: (id: string) => void
}) {
  const visible = records.filter(
    (run) =>
      matchesInvestigation(run, filter) && (!profile || run.initialProfile.join('') === profile),
  )
  return (
    <section className={styles.panel} aria-labelledby="evidence-library-heading">
      <div className={styles.panelHeading}>
        <div>
          <h2 id="evidence-library-heading">Selected evidence</h2>
          <p>
            {visible.length} of {records.length} records · burden values are shown independently
          </p>
        </div>
        <div className={styles.inlineFilters}>
          <label>
            Investigate
            <select
              value={filter}
              onChange={(event) => onFilter(event.target.value as Investigation)}
            >
              {Object.entries(INVESTIGATION_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Initial profile
            <select value={profile} onChange={(event) => onProfile(event.target.value)}>
              <option value="">All selected profiles</option>
              {[...new Set(records.map((run) => run.initialProfile.join('')))]
                .sort()
                .map((value) => (
                  <option key={value}>{value}</option>
                ))}
            </select>
          </label>
        </div>
      </div>
      <div className={styles.tableScroll}>
        <table className={styles.evidenceTable}>
          <caption className="visually-hidden">Selected research evidence</caption>
          <thead>
            <tr>
              <th>Initial profile / analysis</th>
              {INSIGHT_POLICIES.map((policy) => (
                <th key={policy}>{strategyLabel(policy)}</th>
              ))}
              <th>Evidence gaps</th>
              <th>Inspect</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((run) => (
              <tr key={run.id}>
                <th scope="row">
                  <ProfileIndicators
                    profile={run.initialProfile}
                    order={run.provenance.antibioticOrder}
                  />
                  <small>
                    {shortId(run.id)} · {formatDateTime(run.createdAtUtc)}
                  </small>
                </th>
                {INSIGHT_POLICIES.map((policy) => {
                  const result = policyResult(run, policy)
                  return (
                    <td
                      key={policy}
                      className="tabular"
                      style={{ color: result ? STRATEGY_COLORS[policy] : undefined }}
                    >
                      {result
                        ? result.metrics.cumulativeResistanceBurden.toFixed(2)
                        : 'Unavailable'}
                    </td>
                  )
                })}
                <td>
                  {run.strategies.map((result) => (
                    <small key={result.strategy}>
                      {strategyLabel(result.strategy)}: {result.metrics.unsupportedStepCount}/
                      {result.metrics.treatmentSteps} steps
                    </small>
                  ))}
                </td>
                <td>
                  <Button
                    variant="secondary"
                    size="sm"
                    aria-label={`Inspect analysis ${run.id}`}
                    onClick={() => onInspect(run.id)}
                  >
                    Inspect
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!visible.length ? (
        <p className={styles.notice}>
          No selected records match this question. Try another filter or choose more analyses.
        </p>
      ) : null}
      <p className={styles.chartNote}>
        Failure and tie filters use verified, within-analysis comparisons. A lower recorded burden
        is not proof of overall policy superiority.
      </p>
    </section>
  )
}
