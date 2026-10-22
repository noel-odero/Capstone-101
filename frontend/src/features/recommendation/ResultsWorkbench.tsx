import { useId, useState } from 'react'
import { Link } from 'react-router'
import { FiArrowRight, FiCheck } from 'react-icons/fi'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { Tooltip } from '@/components/ui/Tooltip'
import { drugLabel, type AntibioticEntry } from '@/domain/antibiotics'
import { buildTrajectorySeries, formatMetricValue, type MetricKey } from '@/domain/metrics'
import { profileToCode } from '@/domain/profile'
import { outcomeLabel, STRATEGY_NAMES, terminationLabel, GLOSSARY } from '@/domain/terminology'
import type { Comparison, Simulation, StrategyResult } from '@/domain/types'
import { useStepParam } from './useStepParam'
import styles from './results.module.css'

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
  const id = useId()
  const active = strategy === 'baseline' && baseline ? baseline : ppo
  const label = STRATEGY_NAMES[active.strategy]
  const ordered = [...active.steps].sort((a, b) => a.treatmentStepAfter - b.treatmentStepAfter)
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
          <h3>{STRATEGY_NAMES[result.strategy]}</h3>
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
                      <span>{item.treatmentStepAfter}</span>
                      {drugLabel(antibiotics, item.antibiotic)}
                      {item.selectedTargetDrug &&
                      (item.transitionStatus === 'cross_resistance' ||
                        item.transitionStatus === 'collateral_sensitivity') ? (
                        <span className={styles.effectTag}>
                          {item.transitionStatus === 'cross_resistance' ? 'XR' : 'CS'} →{' '}
                          {drugLabel(antibiotics, item.selectedTargetDrug)}
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
            </ol>
          ) : (
            <p className={styles.muted}>No feasible actions were available.</p>
          )}
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
            New simulation <FiArrowRight aria-hidden="true" />
          </ButtonLink>
        }
      />
      <div className={styles.context}>
        <span>
          Starting profile <code>{initial}</code>
        </span>
        <span>
          Scenario <code>{run.provenance.scenarioId}</code>
        </span>
        {comparisonId ? (
          <Link to={`/app/simulation/${comparisonId}`}>
            Open 3D simulation <FiArrowRight aria-hidden="true" />
          </Link>
        ) : null}
      </div>
      <ol className={styles.workflow} aria-label="Completed simulation workflow">
        {[
          ['Configure', 'Starting profile'],
          ['Simulate', 'Strategy evaluation'],
          ['Review', 'Results and evidence'],
        ].map(([title, description], index) => (
          <li key={title}>
            <span>0{index + 1}</span>
            <div>
              <strong>{title}</strong>
              <small>{description}</small>
            </div>
            <FiCheck aria-hidden="true" />
          </li>
        ))}
      </ol>
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
            <section className={styles.summary} aria-labelledby={`${id}-strategy`}>
              <div className={styles.sectionHeading}>
                <p className={styles.eyebrow}>Simulated strategy</p>
                <div className={styles.switcher} role="group" aria-label="Strategy summary">
                  {[ppo, ...(baseline ? [baseline] : [])].map((result) => (
                    <button
                      key={result.strategy}
                      type="button"
                      aria-pressed={active.strategy === result.strategy}
                      onClick={() => {
                        setStrategy(result.strategy === 'ppo' ? 'ppo' : 'baseline')
                        setStep(0)
                      }}
                    >
                      {result.strategy === 'ppo' ? 'PPO' : 'Random baseline'}
                    </button>
                  ))}
                </div>
              </div>
              <h2 id={`${id}-strategy`}>
                {ordered.length
                  ? ordered.map((item) => drugLabel(antibiotics, item.antibiotic)).join(' → ')
                  : 'No feasible antibiotic selections'}
              </h2>
              <p className={styles.muted}>
                {label} · {terminationLabel(active.terminationReason)}
              </p>
              <div className={styles.metrics}>
                {primaryMetrics.map((metric) => (
                  <div key={metric.key}>
                    <span>
                      {metric.label}{' '}
                      <Tooltip label={`Definition of ${metric.label}`}>
                        {run.metricDefinitions[metric.key]?.definition ?? metric.hint}
                      </Tooltip>
                    </span>
                    <strong>{value(active, metric.key)}</strong>
                    <small>{metric.hint}</small>
                  </div>
                ))}
              </div>
              <p className={styles.note}>Susceptibility is a model state, not clinical efficacy.</p>
            </section>
            <section className={styles.section}>
              <div className={styles.sectionHeading}>
                <h2>Order of antibiotics</h2>
                <span className={styles.muted}>Select a step to inspect</span>
              </div>
              {sequences}
            </section>
            {baseline ? (
              <section className={styles.comparisonIntro}>
                <div>
                  <h2>How do the strategies differ?</h2>
                  <p>Compare each outcome under the same starting conditions.</p>
                </div>
                <button type="button" onClick={() => setTab('Compare')}>
                  Compare strategies <FiArrowRight aria-hidden="true" />
                </button>
              </section>
            ) : null}
          </>
        ) : tab === 'Trajectory' ? (
          <section className={styles.section}>
            <h2>Resistance over time</h2>
            <p className={styles.muted}>
              Resistant antibiotics at each saved state. Select a step below to inspect the
              transition.
            </p>
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
              Step on the horizontal axis · resistant antibiotics (0–7) on the vertical axis. Lines
              stop when an episode ends.
            </p>
            {sequences}
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
            <p className={styles.note}>
              {'singleRunCaveat' in run ? run.singleRunCaveat : GLOSSARY.singleRun}
            </p>
            <p className={styles.note}>Greedy comparison is not available in the current model.</p>
            {sequences}
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
                <>
                  <strong>
                    {drugLabel(antibiotics, trace.antibiotic)} →{' '}
                    {drugLabel(antibiotics, trace.selectedTargetDrug)} ·{' '}
                    {trace.transitionStatus === 'cross_resistance'
                      ? 'XR — Cross-resistance'
                      : 'CS — Collateral sensitivity'}
                  </strong>
                  <p>
                    The simulator sampled {trace.transitionStatus === 'cross_resistance' ? 'cross-resistance' : 'collateral sensitivity'} targeting {drugLabel(antibiotics, trace.selectedTargetDrug)} after selecting {drugLabel(antibiotics, trace.antibiotic)}.
                  </p>
                </>
              ) : (
                <>
                  <strong>
                    {trace.hasCandidateTransition ? 'No resistance change' : 'No transition data'}
                  </strong>
                  <p>
                    {trace.hasCandidateTransition
                      ? 'The sampled transition left the resistance profile unchanged.'
                      : 'No candidate transition was available; the simulator kept the profile unchanged.'}
                  </p>
                </>
              )}
              <small>
                The affected target is not necessarily the next antibiotic in the sequence.
              </small>
            </div>
            <dl className={styles.traceGrid}>
              <div>
                <dt>Selected action</dt>
                <dd>{drugLabel(antibiotics, trace.antibiotic)}</dd>
              </div>
              <div>
                <dt>Simulated outcome</dt>
                <dd>{outcomeLabel(trace)}</dd>
              </div>
              <div>
                <dt>Resistance profile</dt>
                <dd>
                  <code>
                    {profileToCode(trace.resistanceProfileBefore)} →{' '}
                    {profileToCode(trace.resistanceProfileAfter)}
                  </code>
                </dd>
              </div>
              <div>
                <dt>Transition support</dt>
                <dd>
                  {trace.hasCandidateTransition
                    ? 'Candidate data available'
                    : 'No candidate transition data'}
                </dd>
              </div>
            </dl>
            <details>
              <summary>Transition evidence and assumptions</summary>
              <dl className={styles.traceGrid}>
                <div>
                  <dt>Scenario</dt>
                  <dd>
                    <code>{run.provenance.scenarioId}</code>
                  </dd>
                </div>
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
              {!trace.hasCandidateTransition ? (
                <p className={styles.note}>{GLOSSARY.unsupported}</p>
              ) : null}
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
            <dt>Scenario / horizon</dt>
            <dd>
              {run.provenance.scenarioId} / {run.provenance.horizon} steps
            </dd>
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
            <dt>Transition coverage</dt>
            <dd>
              {ppo.metrics.unsupportedStepCount} of {ppo.steps.length} PPO steps
              {baseline
                ? `; ${baseline.metrics.unsupportedStepCount} of ${baseline.steps.length} baseline steps`
                : ''}{' '}
              without candidate transition data.
            </dd>
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
        <p className={styles.note}>{run.disclaimer}</p>
      </details>
      <p className={styles.footer}>
        Research simulation only. Not a clinical prescribing recommendation.{' '}
        <Link to="/limitations">Limitations</Link>
      </p>
    </div>
  )
}
