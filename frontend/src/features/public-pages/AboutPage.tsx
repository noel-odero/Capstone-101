import { REPOSITORY_URL } from '@/config/navigation'
import { Link } from 'react-router'
import { PublicPage } from './PublicPage'
import { APP_NAME, APP_TAGLINE } from '@/domain/terminology'

export function AboutPage() {
  return (
    <PublicPage title="About" lede={`${APP_NAME}. ${APP_TAGLINE}`}>
      <section>
        <h2>The question</h2>
        <p>
          How do frozen PPO and DQN policies compare with a random susceptible-action baseline in
          terms of model-derived resistance burden, resistance emergence and the preservation of
          susceptible options?
        </p>
      </section>
      <section>
        <h2>What this is</h2>
        <p>
          A research platform for evaluating antibiotic-selection strategies against a defined
          <em> E. coli</em> resistance model. It compares policies, traces resistance changes and
          preserves the evidence and assumptions behind each analysis. It is not validated for
          clinical prescribing.
        </p>
      </section>
      <section>
        <h2>Who it is for</h2>
        <p>
          Researchers, students and anyone exploring reinforcement learning for
          antimicrobial-stewardship research.
        </p>
      </section>
      <section>
        <h2>How it is built</h2>
        <ul>
          <li>A React interface (this site).</li>
          <li>An ASP.NET Core API that stores account-owned samples and analyses in PostgreSQL.</li>
          <li>
            A Python evaluation engine using frozen PPO and DQN policies and a random baseline.
          </li>
        </ul>
        <p>
          <Link to="/methodology">Methodology</Link> &middot;{' '}
          <Link to="/limitations">Limitations</Link> &middot;{' '}
          <a href={REPOSITORY_URL} rel="noreferrer noopener" target="_blank">
            Source on GitHub
          </a>
        </p>
      </section>
    </PublicPage>
  )
}
