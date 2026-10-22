import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { ProfileActivity, ProfileOverview } from './ProfileOverview'
import { ProfileStrip } from './ProfileStrip'
import { ProfileTabs } from './ProfileTabs'
import { useProfileRun } from './useProfileRun'

const SUBTITLE =
  'The resistance profile of your latest simulation, and the sequence PPO chose for it.'

/** The E. coli Profile: the latest stored run's starting profile, how resistance changes along PPO's sequence, and links to the history. */
export function ProfilePage() {
  const state = useProfileRun()
  const antibiotics = useAntibiotics()

  if (state.status !== 'ready') {
    return (
      <ContentContainer>
        <PageHeader
          title="E. coli Profile"
          subtitle={SUBTITLE}
          action={
            <ButtonLink to="/app/simulation/new" variant="dark">
              Run Simulation
            </ButtonLink>
          }
        />
        {state.status === 'loading' ? (
          <LoadingState label="Loading your latest profile" lines={4} block />
        ) : null}
        {state.status === 'error' ? (
          <ErrorState
            error={state.error}
            title="Your profile could not be loaded"
            onRetry={state.retry}
          />
        ) : null}
        {state.status === 'empty' ? (
          <EmptyState
            title="No profile yet"
            description="Run a simulation and its resistance profile will appear here."
            action={
              <ButtonLink to="/app/simulation/new" variant="dark">
                Run Simulation
              </ButtonLink>
            }
          />
        ) : null}
      </ContentContainer>
    )
  }

  const { run } = state
  return (
    <ContentContainer>
      <PageHeader
        title="E. coli Profile"
        subtitle="View your simulation profile and experiment history."
      />
      <ProfileOverview run={run} />
      <ProfileTabs />
      {antibiotics.isPending ? (
        <LoadingState label="Loading the antibiotics" lines={3} block />
      ) : null}
      {antibiotics.isError ? (
        <ErrorState
          error={antibiotics.error}
          title="The antibiotic list could not be loaded"
          onRetry={() => void antibiotics.refetch()}
        />
      ) : null}
      {antibiotics.data ? (
        <div className="stack-lg">
          <ProfileStrip profile={run.ppo.initialProfile} entries={antibiotics.data} />
          <ProfileActivity run={run} />
        </div>
      ) : null}
    </ContentContainer>
  )
}
