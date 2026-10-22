import { FiArrowRight } from 'react-icons/fi'
import { Link } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { WorkbenchJourney } from './WorkbenchJourney'
import styles from './home.module.css'

export function DashboardPage() {
  return (
    <ContentContainer>
      <div className={styles.home}>
        <header className={styles.welcome}>
          <h1>
            Welcome to
            <br />
            <span>StewardLab</span>
          </h1>
          <p className={styles.intro}>Explore antibiotic choices and resistance over time.</p>
        </header>
        <WorkbenchJourney />
        <section className={styles.launch} aria-labelledby="launch-title">
          <div className={styles.launchCopy}>
            <h2 id="launch-title">Launch the Workbench</h2>
            <p>Start with a resistance profile. Compare what happens next.</p>
            <Link className={styles.launchLink} to="/app/simulation/new">
              Open Workbench <FiArrowRight aria-hidden="true" />
            </Link>
          </div>
          <Link
            className={styles.laptop}
            to="/app/simulation/new"
            aria-label="Open the simulation workbench"
          >
            <div className={styles.screen}>
              <span className={styles.camera} />
              <img
                src="/images/workbench-preview.png"
                alt="StewardLab simulation showing the urinary tract, resistance trajectories and strategy comparison"
              />
            </div>
            <div className={styles.keyboard} />
          </Link>
        </section>
        <p className={styles.footnote}>
          A research prototype, not clinical guidance. <Link to="/limitations">Limitations</Link>
        </p>
      </div>
    </ContentContainer>
  )
}
