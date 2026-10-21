import { useState, useEffect } from 'react'
import { FiPause, FiPlay } from 'react-icons/fi'
import { lazy, Suspense } from 'react'
import type { StrategyResult } from '@/domain/types'
import { lastStepOf } from '@/domain/trajectory'
import styles from './simulation.module.css'
const BacteriaClearanceScene = lazy(() =>
  import('@/features/scene/BacteriaClearanceScene').then((module) => ({
    default: module.BacteriaClearanceScene,
  })),
)
export interface StatePanelProps {
  ppo: StrategyResult
  baseline: StrategyResult
  selectedStep: number
  onSelectStep: (step: number) => void
}
export function StatePanel({
  ppo,
  baseline,
  selectedStep,
  onSelectStep,
}: StatePanelProps) {
  const [playing, setPlaying] = useState(false)
  const last = lastStepOf(ppo.steps, baseline.steps)
  const active = playing && selectedStep < last
  const shownStep = Math.min(selectedStep, ppo.steps.length)
  useEffect(() => {
    if (!active) return
    const timer = setTimeout(() => onSelectStep(selectedStep + 1), 1400)
    return () => clearTimeout(timer)
  }, [active, selectedStep, onSelectStep])
  return (
    <section className={styles['panel']} aria-labelledby="state-title">
      <div className={styles['panelHead']}>
        <h2 id="state-title">Urinary Tract</h2>
        <span className={styles['illustrationLabel']}>Interactive 3D</span>
      </div>
      <ul className={styles['organLegend']}>
        <li>
          <i style={{ background: '#ffad72' }} />
          Bacteria
        </li>
        <li>
          <i style={{ background: '#79e8d2' }} />
          Clearing
        </li>
        <li>
          <i style={{ background: '#927fdd' }} />
          Urinary tract
        </li>
      </ul>
      <div className={styles['clearanceScene']}>
        <Suspense fallback={<p className={styles['organCaption']}>Preparing 3D view…</p>}>
          <BacteriaClearanceScene step={shownStep} horizon={last} />
        </Suspense>
      </div>
      <p className={styles['clearanceNote']}>
        Illustrative clearance only. The model tracks resistance, not bacterial load.
      </p>
      <div className={styles['timeline']}>
        <button
          className={styles['play']}
          type="button"
          aria-label={active ? 'Pause the step animation' : 'Play through the steps'}
          onClick={() => {
            if (active) {
              setPlaying(false)
            } else {
              if (selectedStep >= last) onSelectStep(0)
              setPlaying(true)
            }
          }}
        >
          {active ? <FiPause /> : <FiPlay />}
        </button>
        <ol className={styles['steps']} aria-label="Treatment steps">
          {Array.from({ length: last + 1 }, (_, step) => (
            <li key={step}>
              <button
                className={styles['stepDot']}
                type="button"
                aria-label={step === 0 ? 'Step 0, initial state' : `Step ${step}`}
                aria-pressed={selectedStep === step}
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
