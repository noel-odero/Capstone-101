import { useEffect, useRef, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Button, ButtonLink } from '@/components/ui/Button'
import { buildTrajectorySeries } from '@/domain/metrics'
import { formatDrugName } from '@/domain/antibiotics'
import { useAnalysisLabel } from '@/features/samples/useAnalysisLabel'
import { STRATEGY_COLORS, strategyLabel } from '@/domain/terminology'
import type { StepTrace, StrategyId } from '@/domain/types'
import type { SavedAnalysis } from './history-api'
import styles from './history.module.css'

function transitionLabel(trace: StepTrace, compact = false) {
  if (trace.transitionStatus === 'collateral_sensitivity')
    return compact ? 'CS' : 'CS · Collateral sensitivity'
  if (trace.transitionStatus === 'cross_resistance') return compact ? 'XR' : 'XR · Cross-resistance'
  return trace.hasCandidateTransition
    ? compact
      ? 'No change'
      : 'No resistance change'
    : compact
      ? 'No data'
      : 'No applicable transition data'
}

export function AnalysisInspector({ run, onClose }: { run: SavedAnalysis; onClose: () => void }) {
  const labelFor = useAnalysisLabel()
  const name = labelFor(run)
  const panel = useRef<HTMLElement>(null)
  useEffect(() => {
    panel.current?.focus({ preventScroll: true })
    panel.current?.scrollIntoView?.({ block: 'start' })
  }, [])
  const [strategy, setStrategy] = useState<StrategyId>(run.strategies[0]?.strategy ?? 'ppo')
  const [step, setStep] = useState(1)
  const active = run.strategies.find((result) => result.strategy === strategy)
  const trace = active?.steps.find((item) => item.treatmentStepAfter === step)
  const resultsPath = `/app/recommendations/${run.kind === 'comparison' ? 'comparison' : 'simulation'}/${run.id}`
  return (
    <section ref={panel} tabIndex={-1} className={styles.panel} aria-label={`Details for ${name}`}>
      <div className={styles.panelHeading}>
        <div>
          <h2>{name}</h2>
          <p>{run.provenance.horizon}-step evaluation</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close details
        </Button>
      </div>
      {run.strategies.some((result) => result.terminationReason === 'evidence_boundary') ? (
        <p role="note" className={styles.footnote}>
          An evidence boundary stopped this evaluation. Only recorded states are shown; full-horizon
          burden and final options are unavailable for incomplete strategies.
        </p>
      ) : null}
      <div className={styles.inspectorGrid}>
        <div>
          <h3>Resistance trajectory</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart
              data={buildTrajectorySeries(run.strategies, 'resistantCount')}
              accessibilityLayer
              margin={{ right: 20, bottom: 10 }}
            >
              <CartesianGrid vertical={false} stroke="var(--color-border)" />
              <XAxis dataKey="step" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} />
              <YAxis
                domain={[0, 7]}
                allowDecimals={false}
                width={30}
                tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface)',
                  borderColor: 'var(--color-border)',
                }}
              />
              <Legend />
              {run.strategies.map((result) => (
                <Line
                  key={result.strategy}
                  name={strategyLabel(result.strategy)}
                  dataKey={result.strategy}
                  type="stepAfter"
                  stroke={STRATEGY_COLORS[result.strategy]}
                  strokeDasharray={result.strategy === 'dqn' ? '4 3' : undefined}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          <p className={styles.footnote}>Resistant antibiotics (of 7), by step.</p>
        </div>
        <div>
          <h3>Recorded action sequences</h3>
          {run.strategies.map((result) => (
            <div className={styles.sequence} key={result.strategy}>
              <strong style={{ color: STRATEGY_COLORS[result.strategy] }}>
                {strategyLabel(result.strategy)}
              </strong>
              <ol>
                {result.steps.map((item) => (
                  <li key={item.stepIndex}>
                    <button
                      type="button"
                      aria-pressed={
                        strategy === result.strategy && step === item.treatmentStepAfter
                      }
                      onClick={() => {
                        setStrategy(result.strategy)
                        setStep(item.treatmentStepAfter)
                      }}
                    >
                      <span>{item.treatmentStepAfter}</span>
                      {formatDrugName(item.antibiotic)}
                      <small>{transitionLabel(item, true)}</small>
                    </button>
                  </li>
                ))}
              </ol>
              {!result.steps.length ? (
                <p className={styles.footnote}>No feasible actions were recorded.</p>
              ) : null}
            </div>
          ))}
        </div>
      </div>
      {trace ? (
        <div className={styles.trace}>
          <h3>
            {strategyLabel(strategy)} · Step {step} · {formatDrugName(trace.antibiotic)}
          </h3>
          <dl className={styles.traceValues}>
            <div>
              <dt>Recorded transition</dt>
              <dd>
                {transitionLabel(trace)}
                {trace.selectedTargetDrug ? ` · ${formatDrugName(trace.selectedTargetDrug)}` : ''}
              </dd>
            </div>
            <div>
              <dt>Profile</dt>
              <dd>
                <code>
                  {trace.resistanceProfileBefore.join('')} → {trace.resistanceProfileAfter.join('')}
                </code>
              </dd>
            </div>
            <div>
              <dt>Transition support</dt>
              <dd>
                {trace.hasCandidateTransition
                  ? 'Candidate transition data available'
                  : 'No applicable transition data'}
              </dd>
            </div>
            <div>
              <dt>Source IDs</dt>
              <dd>{trace.sourceIds.join(', ') || 'None for the selected outcome'}</dd>
            </div>
            <div>
              <dt>Scenario probability</dt>
              <dd>
                {trace.selectedCandidateProbability == null
                  ? 'Not available'
                  : `${(trace.selectedCandidateProbability * 100).toFixed(1)}%`}
              </dd>
            </div>
          </dl>
          <p className={styles.footnote}>
            Scenario-assumed probabilities. Transition evidence describes the model outcome, not the
            policy’s internal reasoning.
            {!trace.hasCandidateTransition
              ? ' An unchanged profile on this step reflects missing data, not treatment success.'
              : ''}
          </p>
        </div>
      ) : null}
      <div className={styles.detailLinks}>
        {run.kind === 'comparison' ? (
          <ButtonLink variant="secondary" size="sm" to={`/app/simulation/${run.id}`}>
            Open 3D evaluation
          </ButtonLink>
        ) : null}
        <ButtonLink variant="secondary" size="sm" to={resultsPath}>
          Open Analysis Results
        </ButtonLink>
        <ButtonLink
          variant="ghost"
          size="sm"
          to={`/app/simulation/new?profile=${run.initialProfile.join('')}`}
        >
          Use this initial profile
        </ButtonLink>
      </div>
    </section>
  )
}
