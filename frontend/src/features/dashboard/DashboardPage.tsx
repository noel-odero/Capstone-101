import { FiArrowRight } from 'react-icons/fi'
import { Link } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { WorkbenchJourney } from './WorkbenchJourney'
import { PAGE_TITLES, PROTOTYPE_STATEMENT } from '@/domain/terminology'
import styles from './home.module.css'

export function DashboardPage() {
  return (
    <ContentContainer>
      <div className={styles.home}>
        <header className={styles.welcome}>
          <h1>
            Research
            <br />
            <span>Workspace</span>
          </h1>
          <p className={styles.intro}>
            Evaluate antibiotic strategies. Compare resistance outcomes.
          </p>
        </header>
        <WorkbenchJourney />
        <section className={styles.launch} aria-labelledby="launch-title">
          <div className={styles.launchCopy}>
            <h2 id="launch-title">Evaluate antibiotic strategies</h2>
            <p>Choose a starting profile. Inspect model-derived outcomes.</p>
            <Link className={styles.launchLink} to="/app/simulation/new">
              New Analysis <FiArrowRight aria-hidden="true" />
            </Link>
          </div>
          <Link
            className={styles.laptop}
            to="/app/simulation/new"
            aria-label={`Open ${PAGE_TITLES.evaluation}`}
          >
            <div className={styles.screen}>
              <span className={styles.camera} />
              <img
                src="/images/workbench-preview.png"
                alt="AMR Decision Support 3D analysis page showing the urinary tract, resistance trajectories and PPO, DQN and baseline metrics"
              />
            </div>
            <div className={styles.keyboard} />
          </Link>
        </section>
        <p className={styles.footnote}>
          {PROTOTYPE_STATEMENT} <Link to="/limitations">Limitations</Link>
        </p>
      </div>
    </ContentContainer>
  )
}
