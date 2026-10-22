import { Link } from 'react-router'
import { REPOSITORY_URL } from '@/config/navigation'
import { PublicPage } from './PublicPage'

export function AboutPage() {
  return (
    <PublicPage title="About" lede="A research and educational prototype for studying antibiotic sequencing in a simulated environment.">
      <section>
        <h2>The question</h2>
        <p>
          How does a frozen PPO policy compare with a random susceptible-action baseline in a simulated antibiotic-sequencing
          environment, in terms of resistance burden, resistance emergence and the preservation of susceptible options?
        </p>
      </section>
      <section>
        <h2>What this is</h2>
        <p>
          A simulator of <em>E. coli</em> resistance to seven antibiotics, a trained reinforcement-learning policy, and this
          interface for running and inspecting simulations. It does not recommend treatment for anyone.
        </p>
      </section>
      <section>
        <h2>Who it is for</h2>
        <p>Researchers, students and anyone exploring reinforcement learning for antimicrobial-stewardship research.</p>
      </section>
      <section>
        <h2>How it is built</h2>
        <ul>
          <li>A React interface (this site).</li>
          <li>An ASP.NET Core API that stores each person&apos;s runs in PostgreSQL.</li>
          <li>An internal Python service that runs the frozen PPO checkpoint and the simulator.</li>
        </ul>
        <p>
          <Link to="/methodology">Methodology</Link> &middot; <Link to="/limitations">Limitations</Link> &middot;{' '}
          <a href={REPOSITORY_URL} rel="noreferrer noopener" target="_blank">
            Source on GitHub
          </a>
        </p>
      </section>
    </PublicPage>
  )
}
