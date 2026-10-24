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
import { shortId } from '@/domain/formatters'
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
    <section
      ref={panel}
      tabIndex={-1}
      className={styles.panel}
      aria-label={`Details for analysis ${shortId(run.id)}`}
    >
      <div className={styles.panelHeading}>
        <div>
          <h2>Analysis {shortId(run.id)}</h2>
          <p>
            {run.provenance.scenarioId} · {run.provenance.horizon} steps
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Close details
        </Button>
      </div>
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
      <details className={styles.provenance}>
        <summary>Recorded settings and provenance</summary>
        <dl className={styles.traceValues}>
          <div>
            <dt>Environment / policy seed</dt>
            <dd>
              {run.seedConfiguration.environmentSeed} /{' '}
              {run.seedConfiguration.policySeed ?? 'Not used'}
            </dd>
          </div>
          <div>
            <dt>Pairing verification</dt>
            <dd>
              {run.comparisonVerified === true ? 'Shared conditions verified' : 'Not verified'}
            </dd>
          </div>
          <div>
            <dt>Transition dataset SHA-256</dt>
            <dd>
              <code>{run.provenance.interactionDataSha256 || 'Unknown'}</code>
            </dd>
          </div>
          {run.strategies
            .filter((result) => result.strategy !== 'random_susceptible_baseline')
            .map((result) => {
              const identity =
                result.model ??
                (run.provenance.algorithm ===
                (result.strategy === 'ppo' ? 'MaskablePPO' : 'MaskedDQN')
                  ? run.provenance
                  : null)
              return (
                <div key={result.strategy}>
                  <dt>{strategyLabel(result.strategy)} checkpoint</dt>
                  <dd>
                    {identity?.modelId ?? 'Unknown'}
                    <br />
                    <code>{identity?.checkpointSha256 ?? 'Unknown'}</code>
                  </dd>
                </div>
              )
            })}
          <div>
            <dt>Action order / mask</dt>
            <dd>
              {run.provenance.antibioticOrder.join(', ')}
              <br />
              {run.provenance.actionMaskRule}
            </dd>
          </div>
          <div>
            <dt>Service version</dt>
            <dd>{run.provenance.serviceVersion || 'Unknown'}</dd>
          </div>
        </dl>
        <details>
          <summary>Reward and metric definitions</summary>
          <pre>
            {JSON.stringify(
              { reward: run.provenance.rewardSpecification, metrics: run.metricDefinitions },
              null,
              2,
            )}
          </pre>
        </details>
      </details>
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
