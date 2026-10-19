import { Link } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { RunsTable } from '@/components/scientific/RunsTable'
import { ScientificLimitationsNotice } from '@/components/scientific/ScientificLimitationsNotice'
import { ButtonLink } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { firstName } from '@/domain/runs'
import { RECENT_RUNS_PAGE_SIZE, useRecentRuns } from '@/hooks/useRecentRuns'
import { useAuth } from '@/features/auth/useAuth'
import { OverviewMetrics } from './OverviewMetrics'
import { SequencePromoPanel } from './SequencePromoPanel'
import styles from './dashboard.module.css'

const RECENT_ON_HOME = 5

export function DashboardPage() {
  const { user } = useAuth()
  const recent = useRecentRuns(1, RECENT_RUNS_PAGE_SIZE)

  return (
    <ContentContainer>
      <PageHeader
        title={`Welcome, ${firstName(user?.displayName)}`}
        subtitle="Your latest simulation at a glance."
        action={<ButtonLink to="/app/simulation/new" variant="dark">Run Simulation</ButtonLink>}
      />
      <OverviewMetrics />
      <SequencePromoPanel />

      <section className={styles['section']} aria-labelledby="recent-title">
        <div className={styles['sectionHead']}>
          <h2 id="recent-title">Recent simulations</h2>
          <Link to="/app/history">View all</Link>
        </div>
        {recent.isPending ? <LoadingState label="Loading recent runs" lines={2} /> : null}
        {recent.isError ? <ErrorState error={recent.error} title="Recent runs could not be loaded" onRetry={() => void recent.refetch()} /> : null}
        {recent.data && recent.data.items.length > 0 ? (
          <RunsTable runs={recent.data.items.slice(0, RECENT_ON_HOME)} caption="Your most recent simulations" />
        ) : null}
        {recent.data && recent.data.items.length === 0 ? <p className="muted">Nothing here yet.</p> : null}
      </section>

      <div style={{ marginTop: 'var(--space-6)' }}>
        <ScientificLimitationsNotice />
      </div>
    </ContentContainer>
  )
}
