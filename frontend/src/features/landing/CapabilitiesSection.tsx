import { ArrowRight, Box, ChartColumn, FlaskConical, FolderCog } from 'lucide-react'
import { Link } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { SIGN_IN_PATH, WORKSPACE_PATH } from '@/config/navigation'
import { useAuth } from '@/features/auth/useAuth'
import styles from './landing.module.css'

const CAPABILITIES = [
  { title: 'Run Experiments', text: 'Pick a resistance profile and run both strategies.', icon: FlaskConical, to: '/app/simulation/new' },
  { title: 'View Results', text: 'Compare outcomes and resistance step by step.', icon: ChartColumn, to: '/app/simulation' },
  { title: '3D Visualization', text: 'Watch the seven resistance states change.', icon: Box, to: '/app/simulation' },
  { title: 'Manage Workspace', text: 'Revisit and reopen your past experiments.', icon: FolderCog, to: '/app/history' },
] as const

export function CapabilitiesSection() {
  const auth = useAuth()
  const href = (target: string) => (auth.status === 'authenticated' ? target : `${SIGN_IN_PATH}?returnTo=${encodeURIComponent(target || WORKSPACE_PATH)}`)

  return (
    <ContentContainer>
      <ul className={styles['cards']} style={{ margin: 0, padding: 0, listStyle: 'none' }} aria-label="What you can do">
        {CAPABILITIES.map(({ title, text, icon: Icon, to }) => (
          <li key={title}>
            <Link to={href(to)} className={styles['capability']} style={{ height: '100%' }}>
              <span className={styles['capabilityIcon']}>
                <Icon size={20} aria-hidden="true" />
              </span>
              <h3>{title}</h3>
              <p>{text}</p>
              <ArrowRight size={16} className={styles['arrow']} aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </ContentContainer>
  )
}
