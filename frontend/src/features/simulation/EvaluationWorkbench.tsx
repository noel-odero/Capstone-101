import { useSearchParams } from 'react-router'
import { useState } from 'react'
import { FiRotateCcw } from 'react-icons/fi'
import { Button, ButtonLink } from '@/components/ui/Button'
import { ComparisonMetrics } from '@/components/scientific/ComparisonMetrics'
import { strategyResults } from '@/domain/runs'
import { lastStepOf } from '@/domain/trajectory'
import { STRATEGY_COLORS, strategyLabel } from '@/domain/terminology'
import type { Comparison, StrategyId } from '@/domain/types'
import { useEvaluationPlayback } from './useEvaluationPlayback'
import { StatePanel } from './StatePanel'
import styles from './evaluation.module.css'

export function EvaluationWorkbench({
  comparison,
  autoPlay,
}: {
  comparison: Comparison
  autoPlay: boolean
}) {
  const [params] = useSearchParams()
  const results = strategyResults(comparison)
  const first = results[0]
  const last = lastStepOf(...results.map((result) => result.steps))
  const { state, dispatch } = useEvaluationPlayback(last, autoPlay, Number(params.get('step')) || 0)
  const [policy, setPolicy] = useState<StrategyId>(
    () =>
      results.find((result) => result.strategy === params.get('policy'))?.strategy ??
      first?.strategy ??
      'ppo',
  )
  const active = results.find((result) => result.strategy === policy) ?? first
  if (!active) return null
  return (
    <div className={styles.workbench}>
      <div className={styles.toolbar}>
        <div className={styles.policyTabs} role="group" aria-label="Policy shown in 3D">
          {results.map((result) => (
            <button
              key={result.strategy}
              type="button"
              aria-pressed={active.strategy === result.strategy}
              onClick={() => {
                dispatch({ type: 'pause' })
                setPolicy(result.strategy)
              }}
            >
              <i style={{ background: STRATEGY_COLORS[result.strategy] }} />
              {strategyLabel(result.strategy)}
            </button>
          ))}
        </div>
        {state.completed ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={last === 0}
            onClick={() => {
              dispatch({ type: 'reset' })
              dispatch({ type: 'play' })
            }}
          >
            <FiRotateCcw aria-hidden="true" />
            Replay
          </Button>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => dispatch({ type: 'seek', step: last })}>
            Skip to results
          </Button>
        )}
      </div>
      <StatePanel
        results={results}
        selectedStep={state.step}
        onSelectStep={(step) => dispatch({ type: 'seek', step })}
      />
      {state.completed ? (
        <section className={styles.finalMetrics} aria-labelledby="completion-title">
          <div className={styles.completionHeading}>
            <div>
              <span className={styles.eyebrow}>PLAYBACK COMPLETE</span>
              <h2 id="completion-title">Final strategy comparison</h2>
            </div>
            <ButtonLink
              to={`/app/recommendations/comparison/${comparison.id}`}
              variant="secondary"
              size="sm"
            >
              Open Analysis Results
            </ButtonLink>
          </div>
          <ComparisonMetrics comparison={comparison} />
        </section>
      ) : null}
    </div>
  )
}
