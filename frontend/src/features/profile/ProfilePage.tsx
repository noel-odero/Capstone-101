import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ComparisonNotice } from '@/components/scientific/ComparisonNotice'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { ProfileActivity, ProfileOverview } from './ProfileOverview'
import { ProfileStrip } from './ProfileStrip'
import { useProfileRun } from './useProfileRun'
import styles from './profile.module.css'

const SUBTITLE = 'Inspect your latest profile and resistance trends.'

/** The latest initial profile, strategy resistance trends and recent activity. */
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
              New Analysis
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
            description="Evaluate a strategy and its resistance profile will appear here."
            action={
              <ButtonLink to="/app/simulation/new" variant="dark">
                New Analysis
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
      <div className={styles.profile}>
        <PageHeader title="E. coli Profile" subtitle={SUBTITLE} />
        <ProfileOverview run={run} />
        {run.baseline ? <ComparisonNotice comparison={run} /> : null}
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
      </div>
    </ContentContainer>
  )
}
