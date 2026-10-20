import { ArrowDown, ArrowRight, ArrowUp, Gauge, Pill, ShieldCheck, Stethoscope, type LucideIcon } from 'lucide-react'
import { ErrorState } from '@/components/ui/ErrorState'
import { cx } from '@/components/ui/cx'
import {
  countDelta,
  formatRate,
  percentDelta,
  rateDelta,
  type Delta,
  type RunFigures,
} from '@/domain/homeFigures'
import { useHomeMetrics } from './useHomeMetrics'
import styles from './dashboard.module.css'

type IconTone = 'slate' | 'blue' | 'indigo' | 'green'

interface CardSpec {
  label: string
  icon: LucideIcon
  tone: IconTone
  value: (latest: RunFigures) => string | null
  delta: (latest: RunFigures, previous: RunFigures) => Delta | null
}

/** Each card is one number from the latest PPO result; the change is against the run before it. Nothing is estimated. */
const CARDS: readonly CardSpec[] = [
  {
    label: 'Current Resistance Burden',
    icon: Gauge,
    tone: 'slate',
    value: (latest) => latest.burden.toFixed(2),
    delta: (latest, previous) => percentDelta(latest.burden, previous.burden, false),
  },
  {
    label: 'New Resistant Drugs',
    icon: Pill,
    tone: 'blue',
    value: (latest) => String(latest.newResistant),
    delta: (latest, previous) => percentDelta(latest.newResistant, previous.newResistant, false),
  },
  {
    label: 'Effective Treatments',
    icon: Stethoscope,
    tone: 'indigo',
    value: (latest) => formatRate(latest.susceptibleActionRate),
    delta: (latest, previous) =>
      latest.susceptibleActionRate === null || previous.susceptibleActionRate === null
        ? null
        : rateDelta(latest.susceptibleActionRate, previous.susceptibleActionRate, true),
  },
  {
    label: 'Remaining Susceptible Options',
    icon: ShieldCheck,
    tone: 'green',
    value: (latest) => String(latest.remainingSusceptible),
    delta: (latest, previous) => countDelta(latest.remainingSusceptible, previous.remainingSusceptible, true),
  },
]

const DIRECTION_WORDS = { up: 'Up', down: 'Down', flat: 'Unchanged' } as const
const DIRECTION_ICONS = { up: ArrowUp, down: ArrowDown, flat: ArrowRight } as const

function DeltaBadge({ delta }: { delta: Delta }) {
  const Icon = DIRECTION_ICONS[delta.direction]
  return (
    <span className={cx(styles['delta'], styles[delta.tone])}>
      <Icon size={12} aria-hidden="true" />
      <span className="visually-hidden">{DIRECTION_WORDS[delta.direction]} </span>
      {delta.text}
    </span>
  )
}

function Card({ spec, latest, previous, loading }: { spec: CardSpec; latest: RunFigures | null; previous: RunFigures | null; loading: boolean }) {
  const Icon = spec.icon
  const value = latest ? spec.value(latest) : null
  const delta = latest && previous ? spec.delta(latest, previous) : null
  const caption = loading ? 'Loading' : !latest ? 'Run a simulation to see this' : previous ? 'vs. last simulation' : 'First simulation'
  return (
    <article className={styles['metric']} aria-busy={loading || undefined}>
      <span className={cx(styles['metricIcon'], styles[spec.tone])}>
        <Icon size={18} aria-hidden="true" />
      </span>
      <h2 className={styles['metricLabel']}>{spec.label}</h2>
      <p className={styles['metricRow']}>
        <span className={styles['metricValue']}>{value ?? '\u2014'}</span>
        {delta ? <DeltaBadge delta={delta} /> : null}
      </p>
      <p className={styles['metricCaption']}>{caption}</p>
    </article>
  )
}

export function HomeMetrics() {
  const state = useHomeMetrics()

  if (state.status === 'error') {
    return <ErrorState error={state.error} title="Your latest run could not be loaded" onRetry={state.retry} />
  }
  const latest = state.status === 'ready' ? state.latest : null
  const previous = state.status === 'ready' ? state.previous : null
  return (
    <section className={styles['metrics']} aria-label="Latest simulation">
      {CARDS.map((spec) => (
        <Card key={spec.label} spec={spec} latest={latest} previous={previous} loading={state.status === 'loading'} />
      ))}
    </section>
  )
}
