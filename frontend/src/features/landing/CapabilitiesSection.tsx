import { FiSliders, FiGitBranch, FiLayers, FiArrowUpRight } from 'react-icons/fi'
import { Link } from 'react-router'
import styles from './landing.module.css'
const CAPABILITIES = [
  {
    title: 'Build scenarios',
    text: 'Explore seven-antibiotic resistance profiles.',
    icon: FiSliders,
    to: '/documentation',
  },
  {
    title: 'Compare strategies',
    text: 'Compare policies from the same starting conditions.',
    icon: FiGitBranch,
    to: '/methodology',
  },
  {
    title: 'Trace outcomes',
    text: 'Follow resistance changes, step by step.',
    icon: FiLayers,
    to: '/documentation',
  },
]
export function CapabilitiesSection() {
  return (
    <section id="platform" className={styles['capabilities']} aria-label="Research capabilities">
      <div className={styles['cards']}>
        {CAPABILITIES.map(({ title, text, icon: Icon, to }, index) => (
          <Link key={title} className={styles['capability']} to={to}>
            <div className={styles['capabilityTop']}>
              <Icon />
              <span>0{index + 1}</span>
            </div>
            <h2>
              {title}
              <FiArrowUpRight />
            </h2>
            <p>{text}</p>
          </Link>
        ))}
      </div>
    </section>
  )
}
