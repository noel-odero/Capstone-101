import { Link } from 'react-router'
import { REPOSITORY_URL } from '@/config/navigation'
import { APP_NAME, PROTOTYPE_STATEMENT } from '@/domain/terminology'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function AboutPage() {
  return (
    <PublicPage
      title="About"
      lede="A research platform for model-based antibiotic strategy evaluation."
    >
      <section>
        <h2>About the project</h2>
        <p>
          {APP_NAME}, also known as StewardLab, explores how antibiotic-selection strategies affect
          resistance in a defined E. coli model. It is built for researchers and students
          investigating reinforcement learning for antimicrobial stewardship.
        </p>
      </section>
      <section>
        <h2>What you can do</h2>
        <ul>
          <li>Record and organize labeled sample resistance profiles.</li>
          <li>Compare PPO, DQN, and a random susceptible-action baseline.</li>
          <li>Inspect resistance changes and the evidence behind modeled transitions.</li>
          <li>Revisit saved analyses and investigate patterns across evaluations.</li>
        </ul>
      </section>
      <section>
        <h2>Research scope</h2>
        <p>
          The model represents binary resistance to seven antibiotics. PPO and DQN are trained
          offline and remain frozen during evaluation.
        </p>
        <p className={styles.note}>{PROTOTYPE_STATEMENT}</p>
      </section>
      <section>
        <h2>Further information</h2>
        <p>
          Read the <Link to="/methodology">methodology</Link> and{' '}
          <Link to="/limitations">limitations</Link>, or explore the{' '}
          <a href={REPOSITORY_URL} target="_blank" rel="noreferrer noopener">
            source code on GitHub
          </a>
          .
        </p>
      </section>
    </PublicPage>
  )
}
