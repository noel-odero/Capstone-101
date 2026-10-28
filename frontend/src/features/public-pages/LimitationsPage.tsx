import { Link } from 'react-router'
import { PROTOTYPE_STATEMENT } from '@/domain/terminology'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function LimitationsPage() {
  return (
    <PublicPage
      title="Limitations"
      lede="The scope of the model and the boundaries of its findings."
    >
      <p className={styles.note}>
        {PROTOTYPE_STATEMENT} Do not use this platform to choose antibiotics for a patient.
      </p>
      <section>
        <h2>Simplified representation</h2>
        <p>
          The model uses binary resistance to seven antibiotics, a fixed evaluation horizon, and one
          transition-data scenario. It does not represent a whole infection or patient-specific
          response.
        </p>
        <p>
          Bacterial population size, clearance, dosing, selected-drug self-resistance, and a
          policy-controlled stopping decision are not modeled. Low resistance burden or repeated
          drug selections do not establish clinical suitability.
        </p>
      </section>
      <section>
        <h2>Incomplete transition evidence</h2>
        <p>
          Some susceptible actions lack candidate transition data. These steps leave the profile
          unchanged. They indicate a data gap, not evidence that resistance is stable or treatment
          is effective.
        </p>
      </section>
      <section>
        <h2>Stochastic comparisons</h2>
        <p>
          One evaluation is a single sampled trajectory from a fixed policy. Results can vary
          between runs and do not prove general superiority of PPO, DQN, or the baseline. Different
          actions may produce different outcomes even with the same seed.
        </p>
        <p>
          The random baseline samples among susceptible actions; it is not an exhaustive or optimal
          search. Susceptibility is a model flag, not clinical efficacy.
        </p>
      </section>
      <section>
        <h2>3D illustration</h2>
        <p>
          The urinary-tract scene is an aesthetic illustration. It does not show measured bacterial
          evolution, infection progression, or treatment response.
        </p>
      </section>
      <p>
        Read the <Link to="/methodology">methodology</Link> for how evaluations are performed.
      </p>
    </PublicPage>
  )
}
