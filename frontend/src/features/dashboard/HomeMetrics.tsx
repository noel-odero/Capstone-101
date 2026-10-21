import { FiActivity, FiGitBranch, FiCheckCircle, FiShield } from 'react-icons/fi'
import { ErrorState } from '@/components/ui/ErrorState'
import { Tooltip } from '@/components/ui/Tooltip'
import { useProfileRun } from '@/features/profile/useProfileRun'
import styles from './dashboard.module.css'

/** Values belong to the latest PPO run; unrelated experiments are never compared. */
export function HomeMetrics() {
  const state = useProfileRun()
  if (state.status === 'error')
    return (
      <ErrorState
        error={state.error}
        title="Your latest run could not be loaded"
        onRetry={state.retry}
      />
    )
  const metrics = state.status === 'ready' ? state.run.ppo.metrics : null
  const cards = [
    {
      label: 'Resistance burden',
      icon: FiActivity,
      value: metrics?.cumulativeResistanceBurden.toFixed(2),
      caption: 'Normalized by seven antibiotics',
      definition:
        'Cumulative simulated resistance burden returned by the API, including terminal adjustment. Lower means less simulated burden.',
    },
    {
      label: 'Resistance emergence',
      icon: FiGitBranch,
      value: metrics?.resistanceEmergenceEvents,
      caption: 'Steps with an increased resistant count',
      definition:
        'Counts steps whose resistant-antibiotic count increased, not individual antibiotics.',
    },
    {
      label: 'Susceptible action rate',
      icon: FiCheckCircle,
      value:
        metrics?.susceptibleActionRate == null
          ? undefined
          : `${Math.round(metrics.susceptibleActionRate * 100)}%`,
      caption: 'Selected actions susceptible in the model',
      definition:
        'Share of selected actions that were susceptible in the simulator. This is enforced by the action mask and does not measure clinical treatment effectiveness.',
    },
    {
      label: 'Susceptible options',
      icon: FiShield,
      value: metrics?.finalSusceptibleCount,
      caption: 'Remaining at the end of the run',
      definition:
        'Antibiotics marked susceptible in the final simulated profile. This is not clinical efficacy.',
    },
  ]
  return (
    <section
      className={styles['metrics']}
      aria-label="Latest PPO simulation"
      aria-busy={state.status === 'loading'}
    >
      {cards.map(({ label, icon: Icon, value, caption, definition }) => (
        <article key={label} className={styles['metric']}>
          <Icon size={19} className={styles['metricIcon']} aria-hidden="true" />
          <h2 className={styles['metricLabel']}>
            {label}
            <Tooltip label={`Definition of ${label}`}>{definition}</Tooltip>
          </h2>
          <p className={styles['metricValue']}>{value ?? '\u2014'}</p>
          <p className={styles['metricCaption']}>
            {state.status === 'loading'
              ? 'Loading latest run'
              : !metrics
                ? 'Run an experiment to see results'
                : caption}
          </p>
        </article>
      ))}
    </section>
  )
}
