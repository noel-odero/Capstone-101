import { MapPin } from 'lucide-react'
import { Link } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { PROJECT_LOCATION } from '@/domain/terminology'
import { firstName } from '@/domain/runs'
import { useAuth } from '@/features/auth/useAuth'
import { HomeMetrics } from './HomeMetrics'
import { UrinaryTractPanel } from './UrinaryTractPanel'
import styles from './dashboard.module.css'

export function DashboardPage() {
  const { user } = useAuth()

  return (
    <ContentContainer>
      <PageHeader
        title={`Welcome, ${firstName(user?.displayName)}`}
        subtitle="Smarter antibiotic sequencing. Less resistance. Healthier tomorrows."
        action={
          <span className={styles['location']}>
            <MapPin size={16} aria-hidden="true" />
            {PROJECT_LOCATION}
          </span>
        }
      />
      <HomeMetrics />
      <UrinaryTractPanel />
      <p className={styles['footnote']}>
        A research prototype, not clinical guidance. <Link to="/limitations">Limitations</Link>
      </p>
    </ContentContainer>
  )
}
