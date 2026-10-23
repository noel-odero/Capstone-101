import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { ComparisonNotice } from '@/components/scientific/ComparisonNotice'
import { Tooltip } from '@/components/ui/Tooltip'
import { drugLabel, type AntibioticEntry } from '@/domain/antibiotics'
import {
  buildTrajectorySeries,
  comparePolicyTraces,
  formatMetricValue,
  type MetricKey,
} from '@/domain/metrics'
import { profileToCode } from '@/domain/profile'
import {
  GLOSSARY,
  STRATEGY_NAMES,
  STRATEGY_COLORS,
  strategyLabel,
  terminationLabel,
} from '@/domain/terminology'
import type { Comparison, Simulation, StrategyId, StrategyResult } from '@/domain/types'
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

const comparisonMetrics = [
  { key: 'cumulativeResistanceBurden', label: 'Cumulative resistance burden', hint: '' },
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
  { key: 'unsupportedStepCount', label: 'Steps without applicable transitions', hint: '' },
] as const
const validationMetrics = [
  {
    key: 'susceptibleActionRate',
    label: 'Mask compliance',
    hint: 'Selected drugs were susceptible; enforced by the action mask.',
  },
  {
    key: 'cumulativeAntibioticExposure',
    label: 'Antibiotic exposure',
    hint: 'Run length in actions; not dose or treatment duration.',
  },
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
  const [strategy, setStrategy] = useState<StrategyId>(ppo.strategy)
  const [step, setStep] = useStepParam()
  const sample = useSample('sampleId' in run ? run.sampleId : undefined)
  const id = useId()
  const dqn = 'dqn' in run ? run.dqn : null
  const results = [ppo, ...(dqn ? [dqn] : []), ...(baseline ? [baseline] : [])]
  const active = results.find((result) => result.strategy === strategy) ?? ppo
  const label = STRATEGY_NAMES[active.strategy]
  const trace = active.steps.find((item) => item.treatmentStepAfter === step)
  const initial = profileToCode(ppo.initialProfile)
  const points = buildTrajectorySeries(results, 'resistantCount')
  const pairingVerified = 'contract' in run && run.contract?.verified
  const agreement = dqn && ppo.steps.length ? comparePolicyTraces(ppo, dqn) : null
  const fallbackOnly = results.filter(
    (result) =>
      result.steps.length > 0 && result.metrics.unsupportedStepCount === result.steps.length,
  )

  const metricTable = (
    metrics: readonly { key: MetricKey; label: string; hint: string }[],
    caption: string,
  ) => (
    <div className={styles.tableWrap}>
      <table>
        <caption className="visually-hidden">{caption}</caption>
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
          {metrics.map((metric) => (
            <tr key={metric.key}>
              <th scope="row">
                {metric.label}{' '}
                <Tooltip label={`Definition of ${metric.label}`}>
                  {run.metricDefinitions[metric.key]?.definition ?? metric.hint}
                </Tooltip>
              </th>
              {results.map((result) => (
                <td key={result.strategy}>{value(result, metric.key)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const sequences = (
    <div className={styles.sequences}>
      {results.map((result) => (
        <section
          key={result.strategy}
          aria-label={`${STRATEGY_NAMES[result.strategy]} antibiotic order`}
        >
          <div className={styles.sequenceHeading}>
            <h3>
              <i
                className={styles.strategyDot}
                style={{ background: STRATEGY_COLORS[result.strategy] }}
              />
              {strategyLabel(result.strategy)}
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
                        setStrategy(result.strategy)
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
        {agreement ? (
          <span className={styles.agreement}>
            PPO + DQN ·{' '}
            {agreement.sameChoices
              ? agreement.sameProfiles
                ? 'same sequence'
                : 'same choices, different outcomes'
              : agreement.sameCounts
                ? 'same counts, different choices'
                : 'different trajectories'}
          </span>
        ) : null}
        {comparisonId ? (
          <Link to={`/app/simulation/${comparisonId}`}>
            <FiLayers aria-hidden="true" /> 3D simulation
          </Link>
        ) : null}
      </div>
      {'baseline' in run ? <ComparisonNotice comparison={run} /> : null}
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
                  <XAxis
                    dataKey="step"
                    tick={{ fill: 'var(--color-text-muted)', fontSize: '0.75rem' }}
                  />
                  <YAxis
                    domain={[0, 7]}
                    allowDecimals={false}
                    tick={{ fill: 'var(--color-text-muted)', fontSize: '0.75rem' }}
                  />
                  <ChartTooltip
                    contentStyle={{
                      background: 'var(--color-surface)',
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-text)',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
                  <ReferenceLine x={step} stroke="var(--color-text-muted)" strokeDasharray="3 3" />
                  {results.map((result, index) => (
                    <Line
                      key={result.strategy}
                      name={strategyLabel(result.strategy)}
                      dataKey={result.strategy}
                      stroke={STRATEGY_COLORS[result.strategy]}
                      strokeDasharray={index === 0 ? undefined : index === 1 ? '3 3' : '6 3'}
                      type="stepAfter"
                      strokeWidth={2}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className={styles.note}>
              Step · resistant antibiotics (0–7). Lines stop when an episode ends.
            </p>
            <div className={styles.trajectoryControls}>
              <div className={styles.switcher} role="group" aria-label="Inspect strategy">
                {results.map((result) => (
                  <button
                    key={result.strategy}
                    type="button"
                    aria-pressed={active.strategy === result.strategy}
                    onClick={() => setStrategy(result.strategy)}
                  >
                    {strategyLabel(result.strategy)}
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
                  ? 'Shared starting conditions verified. Lower burden and emergence; more remaining options.'
                  : 'Inspect the recorded assumptions below.'
                : `This saved run contains ${strategyLabel(ppo.strategy)} only. Run a new comparison to evaluate all three strategies.`}
            </p>
            {metricTable(comparisonMetrics, 'Independent simulation outcome metrics')}
            {fallbackOnly.length ? (
              <p className={styles.note} role="note">
                {fallbackOnly.map((result) => strategyLabel(result.strategy)).join(' and ')} had no
                applicable transition in any step. Unchanged resistance reflects the model’s
                fallback rule.
              </p>
            ) : null}
            <details className={styles.validation}>
              <summary>Constraint checks and run length</summary>
              <p className={styles.note}>
                The action mask enforces susceptible selections. Without a recovery or stopping
                model, nonterminal runs last the full horizon. These checks do not establish
                treatment effectiveness.
              </p>
              {metricTable(validationMetrics, 'Simulation constraint checks')}
            </details>
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
                Transition evidence describes the simulator’s outcome. It does not explain a learned
                policy’s internal reasoning for selecting an action.
              </p>
            </details>
          </>
        ) : (
          <p className={styles.muted}>
            {step === 0
              ? 'Select any antibiotic step to inspect its simulated transition.'
              : 'This strategy has no recorded action at the selected step.'}
          </p>
        )}
      </section>
      <details className={styles.assumptions}>
        <summary>Run assumptions and limitations</summary>
        <p className={styles.note}>
          The current model does not include selected-drug self-resistance, bacterial clearance,
          dosing or a stopping decision. Repeated selections and low simulated burden do not
          establish clinical suitability.
        </p>
        <dl className={styles.traceGrid}>
          <div>
            <dt>Run ID</dt>
            <dd>
              <code>{run.id}</code>
            </dd>
          </div>
          {results
            .filter((result) => result.strategy !== 'random_susceptible_baseline')
            .map((result) => {
              const model =
                result.model ?? (result.strategy === ppo.strategy ? run.provenance : null)
              return model ? (
                <div key={result.strategy}>
                  <dt>{strategyLabel(result.strategy)} model / checkpoint</dt>
                  <dd>
                    {model.modelId}
                    <br />
                    <code>{model.checkpointSha256}</code>
                  </dd>
                </div>
              ) : null
            })}
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
