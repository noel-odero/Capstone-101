import { Link } from 'react-router'
import { FiArrowRight, FiMaximize2 } from 'react-icons/fi'
import { useAuth } from '@/features/auth/useAuth'
import styles from './landing.module.css'
export function LandingVisualizationPreview() {
  const auth = useAuth()
  const destination = auth.status === 'authenticated' ? '/app' : '/auth/sign-in?returnTo=%2Fapp'
  return (
    <section className={styles['previewSection']} aria-labelledby="preview-title">
      <div className={styles['previewCopy']}>
        <span className={styles['eyebrow']}>INSIDE THE WORKBENCH</span>
        <h2 id="preview-title">
          From resistance profiles
          <br />
          to simulated outcomes.
        </h2>
        <p>
          A clear view of a complex question. Set a starting profile, compare PPO with the Random
          Susceptible Baseline, and inspect how the modeled state changes after each simulated
          decision.
        </p>
        <Link className={styles['methodLink']} to={destination}>
          Explore the workbench <FiArrowRight />
        </Link>
      </div>
      <figure className={styles['workbenchFrame']}>
        <div className={styles['previewToolbar']}>
          <span>
            <i />
            <i />
            <i />
          </span>
          <span>StewardLab / Simulation</span>
          <FiMaximize2 />
        </div>
        <img
          src="/images/workbench-preview.png"
          alt="Actual workbench interface showing a seven-antibiotic profile, interactive 3D urinary tract, strategy trajectories and comparison metrics"
          width="1440"
          height="1050"
          loading="lazy"
        />
        <figcaption>
          Workbench preview · A single illustrative run, not an aggregate evaluation.
        </figcaption>
      </figure>
    </section>
  )
}
