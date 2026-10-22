import { FiPlay as Play } from 'react-icons/fi'
import { ButtonLink } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { profileToCode } from '@/domain/profile'
import { humanise } from '@/domain/terminology'
import type { ProfileRun } from './useProfileRun'
import styles from './profile.module.css'

/** The model settings of this run, read from its stored provenance. */
export function ModelParameters({ run }: { run: ProfileRun }) {
  const { provenance } = run
  const objective = provenance.rewardSpecification['objective']
  const rows: ReadonlyArray<readonly [string, string]> = [
    ['Algorithm', provenance.algorithm],
    ['Horizon', `${provenance.horizon} steps`],
    ['Antibiotics', String(provenance.antibioticOrder.length)],
    ['Objective', typeof objective === 'string' ? humanise(objective) : 'Not reported'],
    ['Action rule', humanise(provenance.actionMaskRule)],
  ]
  return (
    <Card aria-labelledby="model-title">
      <CardHeader titleId="model-title" title="Model parameters" />
      <dl className={styles['params']}>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <ButtonLink
        to={`/app/simulation/new?profile=${profileToCode(run.ppo.initialProfile)}`}
        className={styles['runButton']}
      >
        <Play size={16} aria-hidden="true" /> Run New Simulation
      </ButtonLink>
    </Card>
  )
}
