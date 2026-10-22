import { FiArrowRight } from 'react-icons/fi'
import { ButtonLink } from '@/components/ui/Button'
import { UrinaryTractIllustration } from './UrinaryTractIllustration'
import styles from './dashboard.module.css'

/** Illustrative anatomy introduces the scientific simulation workflow. */
export function UrinaryTractPanel() {
  return (
    <section className={styles['panel']} aria-labelledby="panel-title">
      <div className={styles['panelCopy']}>
        <h2 id="panel-title">
          See how the right
          <br />
          sequence makes a difference
        </h2>
        <p>
          Compare antibiotic strategies and follow simulated resistance, step by step.
        </p>
        <ButtonLink to="/app/simulation/new" variant="dark">
          Run Simulation <FiArrowRight size={16} aria-hidden="true" />
        </ButtonLink>
      </div>
      <div className={styles['panelEvidence']}>
        <UrinaryTractIllustration className={styles['anatomy']} />
        <div className={styles['burdenLegend']}>
          <strong>Resistance burden</strong>
          <span>
            <i style={{ background: '#ff624e' }} />
            High
          </span>
          <span>
            <i style={{ background: '#ffcc42' }} />
            Medium
          </span>
          <span>
            <i style={{ background: '#61df90' }} />
            Low
          </span>
          <small>Illustrative anatomy</small>
        </div>
      </div>
    </section>
  )
}
