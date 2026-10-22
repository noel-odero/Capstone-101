import { Disclosure } from '@/components/ui/Disclosure'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { formatDateTime, formatProfileSummary, formatSeed, truncateHash } from '@/domain/formatters'
import { profileToCode } from '@/domain/profile'
import type { ModelProvenance, ResistanceProfile, RunStatus, SeedConfiguration } from '@/domain/types'
import styles from './scientific.module.css'

export interface SimulationRunHeaderProps {
  runId: string
  kindLabel: string
  status: RunStatus
  isPersisted: boolean
  createdAtUtc: string
  provenance: ModelProvenance
  seedConfiguration: SeedConfiguration
  initialProfile: ResistanceProfile
  policyLabel?: string
}

/** Identity of a stored run. Primary facts are always visible; hashes and seeds sit behind a disclosure. */
export function SimulationRunHeader({
  runId,
  kindLabel,
  status,
  isPersisted,
  createdAtUtc,
  provenance,
  seedConfiguration,
  initialProfile,
  policyLabel,
}: SimulationRunHeaderProps) {
  return (
    <div className="stack">
      <dl className={styles['summaryGrid']} aria-label={`${kindLabel} details`}>
        <div className={styles['summaryItem']}>
          <dt>{kindLabel} ID</dt>
          <dd className={styles['mono']}>{runId}</dd>
        </div>
        <div className={styles['summaryItem']}>
          <dt>Status</dt>
          <dd>
            <StatusIndicator
              kind={status === 'completed' ? 'susceptible' : 'warning'}
              label={`${status === 'completed' ? 'Completed' : 'Failed'}${isPersisted ? ', stored' : ''}`}
            />
          </dd>
        </div>
        <div className={styles['summaryItem']}>
          <dt>Model</dt>
          <dd>{provenance.modelId}</dd>
        </div>
        {policyLabel ? (
          <div className={styles['summaryItem']}>
            <dt>Policy</dt>
            <dd>{policyLabel}</dd>
          </div>
        ) : null}
        <div className={styles['summaryItem']}>
          <dt>Initial profile</dt>
          <dd>
            <span className={styles['code']}>{profileToCode(initialProfile)}</span>
            <span className="muted"> {formatProfileSummary(initialProfile)}</span>
          </dd>
        </div>
        <div className={styles['summaryItem']}>
          <dt>Horizon</dt>
          <dd>{provenance.horizon} steps</dd>
        </div>
        <div className={styles['summaryItem']}>
          <dt>Created</dt>
          <dd>{formatDateTime(createdAtUtc)}</dd>
        </div>
      </dl>
      <Disclosure summary="Technical details: seeds, model and data hashes">
        <dl className={styles['summaryGrid']}>
          <div className={styles['summaryItem']}>
            <dt>Environment seed</dt>
            <dd>
              {formatSeed(seedConfiguration.environmentSeed)}{' '}
              <span className="muted">({seedConfiguration.environmentSeedSource})</span>
            </dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Policy seed (baseline only)</dt>
            <dd>
              {formatSeed(seedConfiguration.policySeed)}{' '}
              <span className="muted">({seedConfiguration.policySeedSource})</span>
            </dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Algorithm</dt>
            <dd>{provenance.algorithm}</dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Scenario</dt>
            <dd>{provenance.scenarioId}</dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Action mask rule</dt>
            <dd className={styles['mono']}>{provenance.actionMaskRule}</dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Checkpoint SHA-256</dt>
            <dd className={styles['mono']} title={provenance.checkpointSha256}>
              {truncateHash(provenance.checkpointSha256)}
            </dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Transition data SHA-256</dt>
            <dd className={styles['mono']} title={provenance.interactionDataSha256}>
              {truncateHash(provenance.interactionDataSha256)}
            </dd>
          </div>
          <div className={styles['summaryItem']}>
            <dt>Service version</dt>
            <dd>{provenance.serviceVersion}</dd>
          </div>
        </dl>
        {seedConfiguration.notes.length > 0 ? (
          <ul className="muted">
            {seedConfiguration.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </Disclosure>
    </div>
  )
}
