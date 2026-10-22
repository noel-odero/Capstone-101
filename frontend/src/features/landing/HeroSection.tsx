import { FiArrowRight } from 'react-icons/fi'
import { Link } from 'react-router'
import { useAuth } from '@/features/auth/useAuth'
import { ResistanceNetwork } from './ResistanceNetwork'
import styles from './landing.module.css'

export function HeroSection() {
  const auth = useAuth()
  const destination = auth.status === 'authenticated' ? '/app' : '/auth/sign-in?returnTo=%2Fapp'
  return (
    <section className={styles['hero']} aria-labelledby="hero-title">
      <div className={styles['heroGrid']}>
        <div className={styles['heroCopy']}>
          <span className={styles['eyebrow']}>ANTIBIOTIC STEWARDSHIP RESEARCH</span>
          <h1 id="hero-title" className={styles['headline']}>
            Explore the future of antibiotic resistance.
          </h1>
          <p className={styles['lede']}>
            Simulate resistance evolution. Compare strategies. Explore future treatment options.
          </p>
          <div className={styles['actions']}>
            <Link className={styles['launchButton']} to={destination}>
              Launch Workbench{' '}
              <span>
                <FiArrowRight />
              </span>
            </Link>
            <Link className={styles['methodLink']} to="/methodology">
              Explore the Methodology <FiArrowRight />
            </Link>
          </div>
        </div>
        <div className={styles['heroVisual']}>
          <ResistanceNetwork />
        </div>
      </div>
      <div className={styles['heroBottom']}>
        <span>AN EXPLORATORY RESEARCH PLATFORM</span>
        <Link to={destination}>
          Discover the workbench <FiArrowRight aria-hidden="true" />
        </Link>
      </div>
    </section>
  )
}
