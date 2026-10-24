import { FiArrowRight } from 'react-icons/fi'
import { Link } from 'react-router'
import { useAuth } from '@/features/auth/useAuth'
import { PROTOTYPE_STATEMENT } from '@/domain/terminology'
import { ResistanceNetwork } from './ResistanceNetwork'
import styles from './landing.module.css'

export function HeroSection() {
  const auth = useAuth()
  const signedIn = auth.status === 'authenticated'
  const destination = signedIn
    ? '/app/simulation/new'
    : '/auth/sign-in?returnTo=%2Fapp%2Fsimulation%2Fnew'
  const workspaceDestination = signedIn ? '/app' : '/auth/sign-in?returnTo=%2Fapp'
  return (
    <section className={styles['hero']} aria-labelledby="hero-title">
      <div className={styles['heroGrid']}>
        <div className={styles['heroCopy']}>
          <span className={styles['eyebrow']}>AI-POWERED ANTIBIOTIC STRATEGY EVALUATION</span>
          <h1 id="hero-title" className={styles['headline']}>
            Smarter antibiotic strategies begin with better evidence.
          </h1>
          <p className={styles['lede']}>
            Evaluate antibiotic-selection strategies using reinforcement learning. Compare
            resistance outcomes and inspect sequential decisions in a model-based research
            environment.
          </p>
          <div className={styles['actions']}>
            <Link className={styles['launchButton']} to={destination}>
              Start an Analysis{' '}
              <span>
                <FiArrowRight />
              </span>
            </Link>
            <Link className={styles['methodLink']} to="/methodology">
              Explore the Research <FiArrowRight />
            </Link>
          </div>
          <p className={styles.scope}>{PROTOTYPE_STATEMENT}</p>
        </div>
        <div className={styles['heroVisual']}>
          <ResistanceNetwork />
        </div>
      </div>
      <div className={styles['heroBottom']}>
        <span>MODEL-BASED ANTIBIOTIC STRATEGY RESEARCH</span>
        <Link to={workspaceDestination}>
          Open Research Workspace <FiArrowRight aria-hidden="true" />
        </Link>
      </div>
    </section>
  )
}
