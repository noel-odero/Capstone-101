import type { AntibioticEntry } from './antibiotics'
import { drugLabel } from './antibiotics'
import { RESISTANT } from './profile'
import type { StrategyResult } from './types'

export type InsightTone = 'good' | 'info' | 'warn'

export interface Insight {
  id: 'current' | 'first-step' | 'comparison'
  title: string
  text: string
  tone: InsightTone
}

/** Three short statements about the run, each computed from the returned profiles and metrics; nothing is estimated. */
export function buildInsights(ppo: StrategyResult, baseline: StrategyResult | null, entries: readonly AntibioticEntry[]): Insight[] {
  const resistant = entries.filter((entry) => ppo.initialProfile[entry.index] === RESISTANT)
  const codes = resistant.map((entry) => entry.abbreviation ?? entry.displayName).join(', ')

  const current: Insight =
    resistant.length === 0
      ? { id: 'current', title: 'Current resistance', text: 'No antibiotic is resistant in this profile.', tone: 'good' }
      : resistant.length === entries.length
        ? { id: 'current', title: 'Current resistance', text: `All ${entries.length} antibiotics are resistant, so no treatment step is possible.`, tone: 'warn' }
        : { id: 'current', title: 'Current resistance', text: `${resistant.length} of ${entries.length} antibiotics are resistant (${codes}).`, tone: 'warn' }

  const first = ppo.steps[0]
  const distinct = new Set(ppo.steps.map((step) => step.antibiotic)).size
  const firstStep: Insight = first
    ? {
        id: 'first-step',
        title: 'First step',
        text: `PPO starts with ${drugLabel(entries, first.antibiotic)} and uses ${distinct} ${distinct === 1 ? 'antibiotic' : 'different antibiotics'} over ${ppo.steps.length} ${ppo.steps.length === 1 ? 'step' : 'steps'}.`,
        tone: 'info',
      }
    : { id: 'first-step', title: 'First step', text: 'PPO takes no step: no susceptible antibiotic remains.', tone: 'warn' }

  const ppoEnd = ppo.metrics.finalResistantCount
  let comparison: Insight
  if (baseline) {
    const baselineEnd = baseline.metrics.finalResistantCount
    comparison =
      ppoEnd < baselineEnd
        ? { id: 'comparison', title: 'Against the baseline', text: `PPO ends with ${ppoEnd} resistant, the random baseline with ${baselineEnd}.`, tone: 'good' }
        : ppoEnd > baselineEnd
          ? { id: 'comparison', title: 'Against the baseline', text: `PPO ends with ${ppoEnd} resistant, the random baseline with ${baselineEnd}.`, tone: 'warn' }
          : { id: 'comparison', title: 'Against the baseline', text: `PPO and the random baseline both end with ${ppoEnd} resistant.`, tone: 'info' }
  } else {
    const start = ppo.metrics.initialResistantCount
    comparison = {
      id: 'comparison',
      title: 'Over the run',
      text: `Resistant antibiotics went from ${start} at the start to ${ppoEnd} at the end.`,
      tone: ppoEnd < start ? 'good' : ppoEnd > start ? 'warn' : 'info',
    }
  }

  return [current, firstStep, comparison]
}
