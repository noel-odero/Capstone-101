import { FiArrowUpRight, FiGitBranch, FiLayers, FiSliders } from 'react-icons/fi'
import { Link } from 'react-router'
import styles from './home.module.css'

const steps = [
  {
    title: 'Build scenarios',
    description: 'Set your starting resistance profile.',
    to: '/app/simulation/new',
    icon: FiSliders,
  },
  {
    title: 'Compare strategies',
    description: 'Compare PPO with the random baseline.',
    to: '/app/simulation',
    icon: FiGitBranch,
  },
  {
    title: 'Trace outcomes',
    description: 'Follow each decision through time.',
    to: '/app/history',
    icon: FiLayers,
  },
]

export function WorkbenchJourney() {
  return (
    <section className={styles.journey} aria-label="Explore the workbench">
      <div className={styles.steps}>
        {steps.map(({ title, description, to, icon: Icon }) => (
          <Link className={styles.step} to={to} key={title}>
            <Icon className={styles.stepIcon} size={23} aria-hidden="true" />
            <h3>
              {title}
              <FiArrowUpRight size={19} aria-hidden="true" />
            </h3>
            <p>{description}</p>
          </Link>
        ))}
      </div>
    </section>
  )
}
