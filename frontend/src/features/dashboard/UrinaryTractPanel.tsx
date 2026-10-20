import { ArrowRight } from 'lucide-react'
import { ButtonLink } from '@/components/ui/Button'
import { UrinaryTractIllustration } from './UrinaryTractIllustration'
import styles from './dashboard.module.css'

const LEGEND = [
  { label: 'High', className: 'legendHigh' },
  { label: 'Medium', className: 'legendMedium' },
  { label: 'Low', className: 'legendLow' },
] as const

export function UrinaryTractPanel() {
  return (
    <section className={styles['panel']} aria-labelledby="panel-title">
      <div className={styles['panelCopy']}>
        <h2 id="panel-title">See how the right sequence makes a difference</h2>
        <p>Compare a trained PPO policy with a random baseline and watch simulated resistance change step by step.</p>
        <ButtonLink to="/app/simulation/new" variant="dark">
          Run Simulation <ArrowRight size={16} aria-hidden="true" />
        </ButtonLink>
      </div>
      <UrinaryTractIllustration className={styles['panelImage']} />
      <div className={styles['legend']}>
        <p className={styles['legendTitle']}>Resistance burden</p>
        <ul>
          {LEGEND.map(({ label, className }) => (
            <li key={label}>
              <span className={`${styles['legendDot']} ${styles[className]}`} aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
