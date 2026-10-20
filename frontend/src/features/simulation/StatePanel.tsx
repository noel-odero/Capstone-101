import { Pause, Play } from 'lucide-react'
import { lazy, Suspense, useEffect, useState } from 'react'
import { LoadingState } from '@/components/ui/LoadingState'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { drugLabel } from '@/domain/antibiotics'
import { RESISTANT } from '@/domain/profile'
import { actionsFromSteps, lastStepOf, profilesOf, stepAt } from '@/domain/trajectory'
import { STRATEGY_NAMES, terminationLabel } from '@/domain/terminology'
import type { StrategyId, StrategyResult } from '@/domain/types'
import styles from './simulation.module.css'

const ResistanceStateScene = lazy(() => import('@/features/scene/ResistanceStateScene').then((module) => ({ default: module.ResistanceStateScene })))

export interface StatePanelProps {
  ppo: StrategyResult
  baseline: StrategyResult
  antibiotics: readonly AntibioticEntry[]
  selectedStep: number
  onSelectStep: (step: number) => void
}

const PLAY_INTERVAL_MS = 1400

/**
 * The 3D resistance state for the selected strategy and step, with a step timeline. The scene shows only the returned profile:
 * red diamonds are resistant, green spheres susceptible, an amber ring marks what changed, a capsule marks the selected action.
 */
export function StatePanel({ ppo, baseline, antibiotics, selectedStep, onSelectStep }: StatePanelProps) {
  const [strategy, setStrategy] = useState<StrategyId>('ppo')
  const [playing, setPlaying] = useState(false)
  const result = strategy === 'ppo' ? ppo : baseline
  const lastStep = lastStepOf(ppo.steps, baseline.steps)
  const profiles = profilesOf(result)
  const resultLast = profiles.length - 1
  const shownStep = Math.min(selectedStep, resultLast)
  const profile = profiles[shownStep] ?? result.initialProfile
  const previous = shownStep > 0 ? (profiles[shownStep - 1] ?? null) : null
  const actions = actionsFromSteps(result.steps)
  const actionIndex = actions[shownStep] ?? null
  const trace = stepAt(result.steps, shownStep)

  // Playing stops by itself at the last step: it is derived, so no state is set from the effect.
  const active = playing && selectedStep < lastStep
  useEffect(() => {
    if (!active) {
      return
    }
    const timer = window.setTimeout(() => onSelectStep(selectedStep + 1), PLAY_INTERVAL_MS)
    return () => window.clearTimeout(timer)
  }, [active, selectedStep, onSelectStep])

  const changed = new Set<number>()
  if (previous) {
    profile.forEach((state, index) => {
      if (state !== previous[index]) {
        changed.add(index)
      }
    })
  }

  return (
    <section className={styles['panel']} aria-labelledby="state-title">
      <div className={styles['panelHead']}>
        <h2 id="state-title">Resistance state</h2>
        <div className={styles['toggle']} role="group" aria-label="Strategy shown">
          {(['ppo', 'random_susceptible_baseline'] as const).map((id) => (
            <button key={id} type="button" aria-pressed={strategy === id} onClick={() => setStrategy(id)}>
              {id === 'ppo' ? 'PPO' : 'Baseline'}
            </button>
          ))}
        </div>
      </div>

      <div className={styles['scene']}>
        <Suspense fallback={<LoadingState label="Loading the 3D view" lines={1} block />}>
          <ResistanceStateScene entries={antibiotics} profile={profile} previousProfile={previous} selectedActionIndex={actionIndex} />
        </Suspense>
      </div>

      <ul className={styles['sceneLegend']} aria-label="Legend">
        <li>
          <span className={`${styles['legendMark']} ${styles['markSusceptible']}`} aria-hidden="true" />
          S Susceptible
        </li>
        <li>
          <span className={`${styles['legendMark']} ${styles['markResistant']}`} aria-hidden="true" />
          R Resistant
        </li>
        <li>
          <span className={`${styles['legendMark']} ${styles['markChanged']}`} aria-hidden="true" />
          Changed this step
        </li>
      </ul>

      <p className={styles['caption']} aria-live="polite">
        <strong>{shownStep === 0 ? 'Initial state' : `Step ${shownStep}`}</strong>
        {trace ? (
          <span>
            {STRATEGY_NAMES[strategy]} {strategy === 'ppo' ? 'selected' : 'sampled'} {drugLabel(antibiotics, trace.antibiotic)}
          </span>
        ) : shownStep < selectedStep ? (
          <span>Episode ended: {terminationLabel(result.terminationReason)}</span>
        ) : null}
      </p>
      <p className="visually-hidden">
        {antibiotics.map((entry) => `${entry.displayName} ${profile[entry.index] === RESISTANT ? 'resistant' : 'susceptible'}`).join('; ')}
      </p>

      <div className={styles['timeline']}>
        <button
          type="button"
          className={styles['play']}
          aria-label={active ? 'Pause the step animation' : 'Play through the steps'}
          onClick={() => {
            if (active) {
              setPlaying(false)
              return
            }
            if (selectedStep >= lastStep) {
              onSelectStep(0)
            }
            setPlaying(true)
          }}
        >
          {active ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
        </button>
        <ol className={styles['steps']} aria-label="Treatment steps">
          {Array.from({ length: lastStep + 1 }, (_, step) => (
            <li key={step}>
              <button
                type="button"
                className={styles['stepDot']}
                aria-pressed={selectedStep === step}
                aria-label={step === 0 ? 'Step 0, initial state' : `Step ${step}`}
                onClick={() => {
                  setPlaying(false)
                  onSelectStep(step)
                }}
              >
                {step}
              </button>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
