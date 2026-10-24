import { useState } from 'react'
import { FiChevronDown } from 'react-icons/fi'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { drugLabel } from '@/domain/antibiotics'
import type { ProfileEvidence, TransitionEvidenceCandidate } from '@/domain/types'
import { candidateProfile } from './model-states'
import styles from './model-explorer.module.css'

const outcomes = {
  cross_resistance: 'XR',
  collateral_sensitivity: 'CS',
  neutral: 'Neutral',
} as const

function groupedCandidates(candidates: TransitionEvidenceCandidate[]) {
  const groups = new Map<string, TransitionEvidenceCandidate>()
  for (const candidate of candidates) {
    const key = `${candidate.targetDrug}:${candidate.outcome}`
    const previous = groups.get(key)
    groups.set(key, {
      ...candidate,
      sourceIds: [...new Set([...(previous?.sourceIds ?? []), ...candidate.sourceIds])],
    })
  }
  return [...groups.values()]
}

export function TransitionEvidence({
  data,
  entries,
  onSelect,
}: {
  data: ProfileEvidence
  entries: readonly AntibioticEntry[]
  onSelect: (code: string) => void
}) {
  const [expanded, setExpanded] = useState<number | null>(null)
  const supported = data.feasibleActions.filter((action) => action.hasCandidateTransition).length
  const unsupported = data.feasibleActions.length - supported
  return (
    <>
      <div className={styles.stateSummary}>
        <span>
          <strong>{data.resistantCount}</strong> resistant
        </span>
        <span>
          <strong>{data.susceptibleOptionCount}</strong> susceptible
        </span>
        <span>{supported} eligible actions with candidates</span>
      </div>
      <div className={styles.evidenceHeading}>
        <h3>Antibiotics & transition evidence</h3>
        {unsupported > 0 ? (
          <span className={styles.gapCount}>
            {unsupported} {unsupported === 1 ? 'gap' : 'gaps'}
          </span>
        ) : null}
      </div>
      {data.isTerminal ? (
        <p className={styles.terminal}>
          All antibiotics are resistant. No action is eligible from this terminal state.
        </p>
      ) : null}
      <ul className={styles.actions} aria-label="Action eligibility and transition coverage">
        {entries.map((entry) => {
          const eligible = data.resistanceProfile[entry.index] === 0
          const feasible = data.feasibleActions.find((action) => action.actionId === entry.actionId)
          const evidence = data.transitionEvidence.find(
            (action) => action.actionId === entry.actionId,
          )
          const candidates = groupedCandidates(evidence?.candidates ?? [])
          const status = !eligible
            ? 'ineligible'
            : feasible?.hasCandidateTransition
              ? 'supported'
              : 'unsupported'
          return (
            <li key={entry.actionId}>
              <div className={styles.actionRow}>
                <span
                  className={styles.statePill}
                  data-resistant={!eligible}
                  aria-label={eligible ? 'Susceptible' : 'Resistant'}
                >
                  {eligible ? 'S' : 'R'}
                </span>
                <div className={styles.drugIdentity}>
                  <strong>{entry.displayName}</strong>
                  <small>{entry.drugClass ?? `Action ${entry.actionId}`}</small>
                </div>
                {status === 'supported' ? (
                  <button
                    className={styles.evidenceButton}
                    type="button"
                    aria-expanded={expanded === entry.actionId}
                    aria-controls={`action-evidence-${entry.actionId}`}
                    aria-label={`Inspect ${entry.displayName} candidates`}
                    onClick={() => setExpanded(expanded === entry.actionId ? null : entry.actionId)}
                  >
                    <span className={styles.coverage} data-status={status}>
                      Candidates available
                    </span>
                    <FiChevronDown aria-hidden="true" />
                  </button>
                ) : (
                  <span className={styles.coverage} data-status={status}>
                    {status === 'ineligible' ? 'Not eligible' : 'No candidate data'}
                  </span>
                )}
              </div>
              {status === 'supported' && expanded === entry.actionId ? (
                <div className={styles.candidates} id={`action-evidence-${entry.actionId}`}>
                  <p>Possible model outcomes · select a profile to explore</p>
                  {candidates.length === 0 ? (
                    <p>Candidate details are unavailable from this service version.</p>
                  ) : (
                    candidates.map((candidate) => {
                      const next = candidateProfile(data.resistanceProfile, entries, candidate)
                      return (
                        <div
                          className={styles.candidate}
                          key={`${candidate.targetDrug}:${candidate.outcome}`}
                        >
                          <span
                            className={styles.outcome}
                            data-kind={candidate.outcome}
                            title={candidate.outcome.replaceAll('_', ' ')}
                          >
                            {outcomes[candidate.outcome]}
                          </span>
                          <div>
                            <strong>{drugLabel(entries, candidate.targetDrug)}</strong>
                            <small>
                              Sources: {candidate.sourceIds.join(', ') || 'No source ID recorded'}
                            </small>
                          </div>
                          {next && next !== data.resistanceProfile.join('') ? (
                            <button
                              type="button"
                              aria-label={`Explore candidate state ${next}`}
                              onClick={() => onSelect(next)}
                            >
                              <code>{next}</code>
                            </button>
                          ) : (
                            <span className={styles.noChange}>Unchanged</span>
                          )}
                        </div>
                      )
                    })
                  )}
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
      <p className={styles.note}>
        Eligibility means susceptible in this state. Candidate support means a modeled outcome
        exists; it does not establish efficacy or guarantee a resistance change.
      </p>
      <details className={styles.explainer}>
        <summary>Evidence context & model version</summary>
        <p>
          Bits follow the antibiotic row order: 0 = susceptible, 1 = resistant. CS restores target
          susceptibility; XR makes a susceptible target resistant. Source IDs refer to the evidence
          registry. Relationships are modeled possibilities, not measured transition probabilities
          or explanations of policy decisions.
        </p>
        <dl>
          <dt>Scenario</dt>
          <dd>{data.scenarioId ?? 'Not recorded'}</dd>
          <dt>Interaction data SHA-256</dt>
          <dd>
            <code>{data.interactionDataSha256 ?? 'Not recorded'}</code>
          </dd>
        </dl>
      </details>
    </>
  )
}
