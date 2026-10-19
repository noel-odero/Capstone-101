import { CircleDashed } from 'lucide-react'
import { GLOSSARY } from '@/domain/terminology'
import styles from './scientific.module.css'

export interface UnsupportedSummary {
  strategyName: string
  count: number
  total: number
}

export interface TransitionSupportNoticeProps {
  /** Run-level summary: steps without supported transition data per strategy. */
  summaries?: readonly UnsupportedSummary[]
  /** Step-level: the susceptible antibiotic that has no candidate transition in this state. */
  antibiotic?: string
}

/**
 * Explains that "susceptible" and "supported" are different facts. Rendered whenever a step, or a run, includes an
 * action the simulator had no candidate transition data for.
 */
export function TransitionSupportNotice({ summaries, antibiotic }: TransitionSupportNoticeProps) {
  return (
    <div className={`${styles['notice']} ${styles['noticeUnsupported']}`} role="note">
      <CircleDashed size={18} aria-hidden="true" />
      <div className={styles['noticeBody']}>
        <strong>No supported transition data</strong>
        {antibiotic ? <p>{antibiotic} is susceptible in this state, but the simulator has no candidate transition data for it.</p> : null}
        {summaries?.map((summary) => (
          <p key={summary.strategyName}>
            {summary.strategyName}: {summary.count} of {summary.total} selected actions had no supported transition data.
          </p>
        ))}
        <p>{GLOSSARY.unsupported}</p>
        {summaries ? (
          <p>
            Such steps cannot add resistance in the simulation, so read the resistance burden together with this count.
          </p>
        ) : null}
      </div>
    </div>
  )
}
