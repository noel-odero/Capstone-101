import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ProfileEditor } from '@/components/scientific/ProfileEditor'
import { ScientificLimitationsNotice } from '@/components/scientific/ScientificLimitationsNotice'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusIndicator } from '@/components/ui/StatusIndicator'
import { drugLabel } from '@/domain/antibiotics'
import { formatDateTime } from '@/domain/formatters'
import { allSusceptibleProfile, countResistant, countSusceptible, isAllResistant, parseProfileCode, profileToCode } from '@/domain/profile'
import { runDetailPath } from '@/domain/runs'
import { GLOSSARY, transitionSupportLabel } from '@/domain/terminology'
import type { ResistanceProfile } from '@/domain/types'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { useProfileValidation } from '@/hooks/useProfileValidation'
import { useRecentRuns } from '@/hooks/useRecentRuns'
import { ProfileTabs } from './ProfileTabs'
import styles from './profile.module.css'

/** The E. coli profile: seven switches, what is feasible from it, and a way to run a simulation from it. */
export function ProfilePage() {
  const [params, setParams] = useSearchParams()
  const parsed = useMemo(() => parseProfileCode(params.get('profile')), [params])
  const profile: ResistanceProfile = useMemo(() => parsed ?? allSusceptibleProfile(), [parsed])
  const setProfile = (next: ResistanceProfile) => setParams({ profile: profileToCode(next) }, { replace: true })

  const antibiotics = useAntibiotics()
  const validation = useProfileValidation(profile)
  const recent = useRecentRuns(1, 5)
  const terminal = isAllResistant(profile)

  return (
    <ContentContainer>
      <PageHeader
        title="E. coli Profile"
        subtitle="Set the simulated resistance profile, then run a simulation from it."
        action={
          terminal ? (
            <Button variant="dark" disabled>
              Run Simulation
            </Button>
          ) : (
            <ButtonLink to={`/app/simulation/new?profile=${profileToCode(profile)}`} variant="dark">
              Run Simulation
            </ButtonLink>
          )
        }
      />
      <ProfileTabs />

      <div className={styles['grid']}>
        <div className="stack-lg">
          <Card aria-labelledby="profile-title">
            <CardHeader titleId="profile-title" title="Current resistance profile" />
            {antibiotics.isPending ? <LoadingState label="Loading antibiotics" lines={2} block /> : null}
            {antibiotics.isError ? <ErrorState error={antibiotics.error} onRetry={() => void antibiotics.refetch()} /> : null}
            {antibiotics.data ? <ProfileEditor entries={antibiotics.data} profile={profile} onChange={setProfile} /> : null}
          </Card>

          <Card aria-labelledby="feasible-title">
            <CardHeader titleId="feasible-title" title="From this profile" />
            <div className="stack">
              <dl className={styles['summary']}>
                <div>
                  <dt>Susceptible</dt>
                  <dd>{countSusceptible(profile)} of 7</dd>
                </div>
                <div>
                  <dt>Resistant</dt>
                  <dd>{countResistant(profile)} of 7</dd>
                </div>
                <div>
                  <dt>Feasible actions</dt>
                  <dd>{validation.data ? validation.data.feasibleActions.length : '\u2026'}</dd>
                </div>
              </dl>
              {validation.isPending ? <LoadingState label="Checking with the simulator" lines={1} /> : null}
              {validation.isError ? <ErrorState error={validation.error} title="The profile could not be checked" onRetry={() => void validation.refetch()} /> : null}
              {validation.data?.isTerminal ? (
                <p role="note">
                  <StatusIndicator kind="warning" label="No feasible actions remain" /> {GLOSSARY.noFeasibleActions}
                </p>
              ) : null}
              {validation.data && !validation.data.isTerminal && antibiotics.data ? (
                <ul className={styles['feasible']} aria-label="Feasible actions and their transition data">
                  {validation.data.feasibleActions.map((action) => (
                    <li key={action.actionId}>
                      {drugLabel(antibiotics.data, action.antibiotic)}
                      <StatusIndicator kind={action.hasCandidateTransition ? 'supported' : 'unsupported'} label={transitionSupportLabel(action.hasCandidateTransition)} />
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </Card>
        </div>

        <div className="stack-lg">
          <Card aria-labelledby="activity-title">
            <CardHeader titleId="activity-title" title="Recent activity" actions={<Link to="/app/history">View all</Link>} />
            {recent.isPending ? <LoadingState label="Loading activity" lines={2} /> : null}
            {recent.isError ? <ErrorState error={recent.error} onRetry={() => void recent.refetch()} /> : null}
            {recent.data && recent.data.items.length === 0 ? <p className="muted">No simulations yet.</p> : null}
            {recent.data && recent.data.items.length > 0 ? (
              <ul className={styles['activity']}>
                {recent.data.items.map((run) => {
                  const path = runDetailPath(run)
                  return (
                    <li key={run.id}>
                      <span>
                        {run.kind === 'comparison' ? 'Comparison' : 'Simulation'} on <span className={styles['mono']}>{profileToCode(run.initialProfile)}</span>
                      </span>
                      <span className="muted">
                        {formatDateTime(run.createdAtUtc)} {path ? <>&middot; <Link to={path}>Open</Link></> : null}
                      </span>
                    </li>
                  )
                })}
              </ul>
            ) : null}
          </Card>
          <ScientificLimitationsNotice />
        </div>
      </div>
    </ContentContainer>
  )
}
