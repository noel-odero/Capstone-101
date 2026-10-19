import type { AntibioticEntry } from '@/domain/antibiotics'
import { GLOSSARY, transitionSupportLabel } from '@/domain/terminology'
import { RESISTANT } from '@/domain/profile'
import type { ResistanceState } from '@/domain/types'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import styles from './scientific.module.css'

export interface AntibioticStatusProps {
  antibiotic: Pick<AntibioticEntry, 'displayName' | 'abbreviation' | 'drugClass'>
  state: ResistanceState
  /** Whether candidate transition data exist for this antibiotic in the current state; omitted when unknown. */
  hasCandidateTransition?: boolean | undefined
}

/** Susceptibility and transition support are two separate statements and are rendered as two separate indicators. */
export function AntibioticStatus({ antibiotic, state, hasCandidateTransition }: AntibioticStatusProps) {
  const resistant = state === RESISTANT
  return (
    <div className={styles['cellStack']}>
      <span className={styles['tileName']}>
        <strong>{antibiotic.displayName}</strong>
        {antibiotic.abbreviation ? <span className="muted"> ({antibiotic.abbreviation})</span> : null}
      </span>
      <StatusIndicator
        kind={resistant ? 'resistant' : 'susceptible'}
        label={resistant ? 'Resistant' : 'Susceptible'}
        title={resistant ? GLOSSARY.resistant : GLOSSARY.susceptible}
      />
      {hasCandidateTransition === undefined || resistant ? null : (
        <StatusIndicator
          kind={hasCandidateTransition ? 'supported' : 'unsupported'}
          label={transitionSupportLabel(hasCandidateTransition)}
          title={hasCandidateTransition ? GLOSSARY.supported : GLOSSARY.unsupported}
        />
      )}
    </div>
  )
}
