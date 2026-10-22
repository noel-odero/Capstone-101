import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { Tooltip } from '@/components/ui/Tooltip'
import { drugLabel, type AntibioticEntry } from '@/domain/antibiotics'
import { buildTrajectorySeries, formatMetricValue, type MetricKey } from '@/domain/metrics'
import { profileToCode } from '@/domain/profile'
import { GLOSSARY, STRATEGY_NAMES, terminationLabel } from '@/domain/terminology'
import type { Comparison, Simulation, StrategyResult } from '@/domain/types'
import { useSample } from '@/features/samples/useSamples'
import { useId, useState } from 'react'
import { FiArrowRight, FiCheck, FiLayers } from 'react-icons/fi'
import { Link } from 'react-router'
import {
  CartesianGrid,
  Tooltip as ChartTooltip,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import styles from './results.module.css'
import { useStepParam } from './useStepParam'

const primaryMetrics = [
  {
    key: 'susceptibleActionRate',
    label: 'Susceptible selections',
    hint: 'Selections marked susceptible in the model',
  },
  {
    key: 'resistanceEmergenceEvents',
    label: 'Resistance emergence',
    hint: 'Steps with increasing resistance',
  },
  {
    key: 'finalSusceptibleCount',
    label: 'Remaining options',
    hint: 'Susceptible antibiotics at the end',
  },
  {
    key: 'cumulativeAntibioticExposure',
    label: 'Antibiotic exposure',
    hint: 'Administrations in the simulation',
  },
] as const
const comparisonMetrics = [
  ...primaryMetrics,
  { key: 'cumulativeResistanceBurden', label: 'Cumulative resistance burden', hint: '' },
  { key: 'unsupportedStepCount', label: 'Steps without transition data', hint: '' },
] as const
const tabs = ['Overview', 'Trajectory', 'Compare'] as const

function value(result: StrategyResult, key: MetricKey) {
  const raw = result.metrics[key]
  if (raw == null) return 'Not available'
  if (key === 'susceptibleActionRate') return `${Math.round(raw * 100)}%`
  if (key === 'finalSusceptibleCount') return `${raw} / 7`
  return formatMetricValue(key, raw)
}

export function ResultsWorkbench({
  run,
  ppo,
  baseline,
  antibiotics,
  comparisonId,
}: {
  run: Comparison | Simulation
  ppo: StrategyResult
  baseline: StrategyResult | null
  antibiotics: readonly AntibioticEntry[]
  comparisonId: string | undefined
}) {
  const [tab, setTab] = useState<(typeof tabs)[number]>('Overview')
  const [strategy, setStrategy] = useState<'ppo' | 'baseline'>('ppo')
  const [step, setStep] = useStepParam()
  const sample = useSample('sampleId' in run ? run.sampleId : undefined)
  const id = useId()
  const active = strategy === 'baseline' && baseline ? baseline : ppo
  const label = STRATEGY_NAMES[active.strategy]
  const trace = active.steps.find((item) => item.treatmentStepAfter === step)
  const initial = profileToCode(ppo.initialProfile)
  const points = baseline
    ? buildTrajectorySeries(ppo, baseline, 'resistantCount')
    : ppo.states.map((state) => ({
        step: state.stateIndex,
        ppo: state.resistantCount,
        baseline: null,
      }))
  const pairingVerified = 'contract' in run && run.contract?.verified

  const sequences = (
    <div className={styles.sequences}>
      {[ppo, ...(baseline ? [baseline] : [])].map((result) => (
        <section
          key={result.strategy}
          aria-label={`${STRATEGY_NAMES[result.strategy]} antibiotic order`}
        >
          <div className={styles.sequenceHeading}>
            <h3>
              <i className={result.strategy === 'ppo' ? styles.ppoDot : styles.baselineDot} />
              {result.strategy === 'ppo' ? 'PPO strategy' : 'Random baseline'}
            </h3>
            <span>{result.steps.length} steps</span>
          </div>
          {result.steps.length ? (
            <ol className={styles.sequence}>
              {[...result.steps]
                .sort((a, b) => a.treatmentStepAfter - b.treatmentStepAfter)
                .map((item) => (
                  <li key={item.stepIndex}>
                    <button
                      type="button"
                      aria-pressed={
                        active.strategy === result.strategy && step === item.treatmentStepAfter
                      }
                      onClick={() => {
                        setStrategy(result.strategy === 'ppo' ? 'ppo' : 'baseline')
                        setStep(item.treatmentStepAfter)
                      }}
                    >
                      <span className={styles.stepNumber}>{item.treatmentStepAfter}</span>
                      <span className={styles.drugName}>
                        {drugLabel(antibiotics, item.antibiotic)}
                      </span>
                      {item.selectedTargetDrug &&
                      (item.transitionStatus === 'cross_resistance' ||
                        item.transitionStatus === 'collateral_sensitivity') ? (
                        <span className={styles.effectTag}>
                          <b data-effect={item.transitionStatus}>
                            {item.transitionStatus === 'cross_resistance' ? 'XR' : 'CS'}
                          </b>
                          <span>{drugLabel(antibiotics, item.selectedTargetDrug)}</span>
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
            </ol>
          ) : (
            <p className={styles.muted}>No feasible actions were available.</p>
          )}
          <p className={styles.note}>{terminationLabel(result.terminationReason)}</p>
        </section>
      ))}
    </div>
  )

  return (
    <div className={styles.results}>
      <div className={styles.topline}>
        <span>Stewardship / Results</span>
        <span className={styles.completed}>
          <FiCheck aria-hidden="true" /> Completed
        </span>
      </div>
      <PageHeader
        title="Results and Recommendations"
        subtitle={`E. coli resistance model · 7 antibiotics · ${run.provenance.horizon}-step horizon`}
        action={
          <ButtonLink to={`/app/simulation/new?profile=${initial}`} variant="secondary" size="sm">
            New simulation
          </ButtonLink>
        }
      />
      <div className={styles.context}>
        {sample.data ? <Link to="/app/samples">Sample: {sample.data.label}</Link> : null}
        <span>
          Starting profile <code>{initial}</code>
        </span>
        {comparisonId ? (
          <Link to={`/app/simulation/${comparisonId}`}>
            <FiLayers aria-hidden="true" /> 3D simulation
          </Link>
        ) : null}
      </div>
      <div className={styles.tabs} role="tablist" aria-label="Simulation results">
        {tabs.map((name, index) => (
          <button
            key={name}
            type="button"
            role="tab"
            id={`${id}-${name}`}
            aria-selected={tab === name}
            aria-controls={`${id}-panel`}
            tabIndex={tab === name ? 0 : -1}
            onClick={() => setTab(name)}
            onKeyDown={(event) => {
              const next =
                event.key === 'ArrowRight'
                  ? (index + 1) % tabs.length
                  : event.key === 'ArrowLeft'
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === 'Home'
                      ? 0
                      : event.key === 'End'
                        ? tabs.length - 1
                        : null
              if (next !== null) {
                event.preventDefault()
                const nextTab = tabs[next]
                if (nextTab) {
                  setTab(nextTab)
                  document.getElementById(`${id}-${nextTab}`)?.focus()
                }
              }
            }}
          >
            {name}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel`}
        aria-labelledby={`${id}-${tab}`}
        className={styles.tabContent}
      >
        {tab === 'Overview' ? (
          <>
            <section className={styles.section}>
              <div className={styles.sectionHeading}>
                <h2>Order of antibiotics</h2>
                {baseline ? (
                  <button
                    className={styles.textButton}
                    type="button"
                    onClick={() => setTab('Compare')}
                  >
                    Compare strategies <FiArrowRight aria-hidden="true" />
                  </button>
                ) : null}
              </div>
              <p className={styles.sequenceHint}>
                Select any step for its transition details.{' '}
                <span>CS: collateral sensitivity · XR: cross-resistance</span>
              </p>
              {sequences}
            </section>
          </>
        ) : tab === 'Trajectory' ? (
          <section className={styles.section}>
            <h2>Resistance over time</h2>
            <p className={styles.muted}>Resistant antibiotics by simulation step.</p>
            <div className={styles.chart}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points} margin={{ top: 15, right: 20, bottom: 10, left: -20 }}>
                  <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                  <XAxis dataKey="step" tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} />
                  <YAxis
                    domain={[0, 7]}
                    allowDecimals={false}
                    tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }}
                  />
                  <ChartTooltip
                    contentStyle={{
                      background: 'var(--color-surface)',
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text)',
                    }}
                  />
                  <Legend />
                  <ReferenceLine x={step} stroke="var(--color-text-muted)" strokeDasharray="3 3" />
                  <Line
                    name="PPO"
                    dataKey="ppo"
                    stroke="var(--color-series-ppo)"
                    strokeWidth={2}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                  {baseline ? (
                    <Line
                      name="Random baseline"
                      dataKey="baseline"
                      stroke="var(--color-series-baseline)"
                      strokeWidth={2}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  ) : null}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className={styles.note}>
              Step · resistant antibiotics (0–7). Lines stop when an episode ends.
            </p>
            <div className={styles.trajectoryControls}>
              <div className={styles.switcher} role="group" aria-label="Inspect strategy">
                {[ppo, ...(baseline ? [baseline] : [])].map((result) => (
                  <button
                    key={result.strategy}
                    type="button"
                    aria-pressed={active.strategy === result.strategy}
                    onClick={() => setStrategy(result.strategy === 'ppo' ? 'ppo' : 'baseline')}
                  >
                    {result.strategy === 'ppo' ? 'PPO' : 'Random baseline'}
                  </button>
                ))}
              </div>
              <label>
                Step {step}
                <input
                  type="range"
                  aria-label="Inspect treatment step"
                  min={0}
                  max={run.provenance.horizon}
                  value={step}
                  onChange={(event) => setStep(Number(event.target.value))}
                />
              </label>
            </div>
          </section>
        ) : (
          <section className={styles.section}>
            <h2>Compare simulated strategies</h2>
            <p className={styles.muted}>
              {baseline
                ? pairingVerified
                  ? 'Shared starting conditions verified for this paired run.'
                  : 'Paired run. Inspect the recorded assumptions below.'
                : 'This saved run contains PPO only. Run a new comparison to evaluate both strategies.'}
            </p>
            <div className={styles.tableWrap}>
              <table>
                <caption className="visually-hidden">
                  Independent simulation outcome metrics
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Metric</th>
                    <th scope="col">PPO</th>
                    {baseline ? <th scope="col">Random baseline</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {comparisonMetrics.map((metric) => (
                    <tr key={metric.key}>
                      <th scope="row">
                        {metric.label}{' '}
                        <Tooltip label={`Definition of ${metric.label}`}>
                          {run.metricDefinitions[metric.key]?.definition ?? metric.hint}
                        </Tooltip>
                      </th>
                      <td>{value(ppo, metric.key)}</td>
                      {baseline ? <td>{value(baseline, metric.key)}</td> : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className={styles.note}>Greedy comparison is not available in the current model.</p>
          </section>
        )}
      </div>
      <section className={styles.inspector} aria-labelledby={`${id}-trace`}>
        <div className={styles.sectionHeading}>
          <h2 id={`${id}-trace`}>Decision trace</h2>
          <span>
            {label} · {step === 0 ? 'Initial state' : `Step ${step}`}
          </span>
        </div>
        {trace ? (
          <>
            <div className={styles.effectSummary}>
              {trace.selectedTargetDrug &&
              (trace.transitionStatus === 'cross_resistance' ||
                trace.transitionStatus === 'collateral_sensitivity') ? (
                <div className={styles.effectPair}>
                  <div>
                    <small>Selected drug</small>
                    <strong>{drugLabel(antibiotics, trace.antibiotic)}</strong>
                  </div>
                  <span className={styles.effectBadge} data-effect={trace.transitionStatus}>
                    {trace.transitionStatus === 'cross_resistance' ? 'XR' : 'CS'}
                  </span>
                  <div>
                    <small>Affected drug</small>
                    <strong>{drugLabel(antibiotics, trace.selectedTargetDrug)}</strong>
                  </div>
                </div>
              ) : (
                <>
                  <strong>
                    {drugLabel(antibiotics, trace.antibiotic)} ·{' '}
                    {trace.hasCandidateTransition ? 'No resistance change' : 'No transition data'}
                  </strong>
                  <p>
                    Profile unchanged
                    {trace.hasCandidateTransition
                      ? ' in this step.'
                      : '; transition evidence unavailable.'}
                  </p>
                </>
              )}
              <small>
                Simulated effect; the target may differ from the next drug in the sequence.
              </small>
            </div>
            <details>
              <summary>Transition evidence and assumptions</summary>
              <dl className={styles.traceGrid}>
                <div>
                  <dt>Resistance profile</dt>
                  <dd>
                    <code>
                      {profileToCode(trace.resistanceProfileBefore)} →{' '}
                      {profileToCode(trace.resistanceProfileAfter)}
                    </code>
                  </dd>
                </div>
              </dl>
              <dl className={styles.traceGrid}>
                <div>
                  <dt>Sampled outcome probability</dt>
                  <dd>
                    {trace.selectedCandidateProbability == null
                      ? 'Not available'
                      : `${(trace.selectedCandidateProbability * 100).toFixed(1)}%`}{' '}
                    · scenario-assumed, not empirical
                  </dd>
                </div>
                <div>
                  <dt>Source IDs returned by the model</dt>
                  <dd>
                    {trace.sourceIds.length
                      ? trace.sourceIds.map((source) => <code key={source}>{source} </code>)
                      : 'No source IDs returned for this step'}
                  </dd>
                </div>
                <div>
                  <dt>New resistance / susceptibility</dt>
                  <dd>
                    {trace.newlyResistantAntibiotics
                      .map((name) => drugLabel(antibiotics, name))
                      .join(', ') || 'No new resistance'}{' '}
                    /{' '}
                    {trace.newlySusceptibleAntibiotics
                      .map((name) => drugLabel(antibiotics, name))
                      .join(', ') || 'No new susceptibility'}
                  </dd>
                </div>
              </dl>
              <p className={styles.note}>
                Transition evidence describes the simulator’s outcome. It does not explain PPO’s
                internal reasoning for selecting an action.
              </p>
            </details>
          </>
        ) : (
          <p className={styles.muted}>
            {step === 0
              ? 'Select an antibiotic in either sequence to inspect its simulated transition.'
              : 'This strategy has no recorded action at the selected step.'}
          </p>
        )}
      </section>
      <details className={styles.assumptions}>
        <summary>Run assumptions and limitations</summary>
        <dl className={styles.traceGrid}>
          <div>
            <dt>Run ID</dt>
            <dd>
              <code>{run.id}</code>
            </dd>
          </div>
          <div>
            <dt>Model / algorithm</dt>
            <dd>
              {run.provenance.modelId} / {run.provenance.algorithm}
            </dd>
          </div>
          <div>
            <dt>Scenario</dt>
            <dd>{run.provenance.scenarioId}</dd>
          </div>
          <div>
            <dt>Environment / policy seeds</dt>
            <dd>
              {run.seedConfiguration.environmentSeed} /{' '}
              {run.seedConfiguration.policySeed ?? 'Not specified'}
            </dd>
          </div>
          <div>
            <dt>Action mask</dt>
            <dd>{run.provenance.actionMaskRule}</dd>
          </div>
          <div>
            <dt>Checkpoint SHA-256</dt>
            <dd>
              <code>{run.provenance.checkpointSha256}</code>
            </dd>
          </div>
          <div>
            <dt>Interaction data SHA-256</dt>
            <dd>
              <code>{run.provenance.interactionDataSha256}</code>
            </dd>
          </div>
        </dl>
        <p className={styles.note}>{GLOSSARY.unsupported}</p>
        <p className={styles.note}>{GLOSSARY.sameSeed}</p>
        {run.seedConfiguration.notes.map((note) => (
          <p key={note} className={styles.note}>
            {note}
          </p>
        ))}
        <p className={styles.note}>
          {'singleRunCaveat' in run ? run.singleRunCaveat : GLOSSARY.singleRun}
        </p>
      </details>
      <p className={styles.footer}>
        Research simulation only. Not a clinical prescribing recommendation.{' '}
        <Link to="/limitations">Limitations</Link>
      </p>
    </div>
  )
}
