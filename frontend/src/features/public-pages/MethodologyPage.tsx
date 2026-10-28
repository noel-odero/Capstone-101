import { REPOSITORY_URL } from '@/config/navigation'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function MethodologyPage() {
  return (
    <PublicPage
      title="Methodology"
      lede="How strategies are evaluated and how to interpret the results."
    >
      <section>
        <h2>Evaluation process</h2>
        <ol>
          <li>
            Choose a starting resistance profile across seven antibiotics: 0 is susceptible and 1 is
            resistant.
          </li>
          <li>Each strategy selects an antibiotic from those currently marked susceptible.</li>
          <li>
            The engine samples a modeled outcome from candidate transitions for that action and
            state.
          </li>
          <li>Repeat for up to eight steps, ending earlier if no susceptible action remains.</li>
        </ol>
        <p>
          The 128 possible profiles are mathematical model states, not measured E. coli isolates.
        </p>
      </section>
      <section>
        <h2>Strategies</h2>
        <dl className={styles.definitions}>
          <div>
            <dt>PPO</dt>
            <dd>A frozen Proximal Policy Optimization policy.</dd>
          </div>
          <div>
            <dt>DQN</dt>
            <dd>A frozen Deep Q-Network policy.</dd>
          </div>
          <div>
            <dt>Random baseline</dt>
            <dd>
              Samples uniformly among susceptible antibiotics. It does not search for an optimal
              sequence.
            </dd>
          </div>
        </dl>
        <p>All three use the same susceptibility-based action mask and starting conditions.</p>
      </section>
      <section>
        <h2>Transition evidence</h2>
        <p>
          Action eligibility and transition support are separate. A susceptible antibiotic may have
          no candidate transition data for the current state. In that case, the profile stays
          unchanged; this does not establish stability or treatment effectiveness.
        </p>
      </section>
      <section>
        <h2>Evaluation metrics</h2>
        <dl className={styles.definitions}>
          <div>
            <dt>Resistance burden</dt>
            <dd>
              Sum of resistant-drug fractions over the steps. An all-resistant state is charged for
              the remaining horizon. Lower indicates less modeled burden.
            </dd>
          </div>
          <div>
            <dt>Resistance emergence</dt>
            <dd>Steps in which the number of resistant antibiotics increased.</dd>
          </div>
          <div>
            <dt>Susceptible options</dt>
            <dd>Antibiotics still marked susceptible at the end.</dd>
          </div>
          <div>
            <dt>Susceptible-action rate</dt>
            <dd>
              The share of actions eligible under the mask. This is 1.0 for strategies that act, not
              a measure of clinical effectiveness.
            </dd>
          </div>
        </dl>
      </section>
      <section>
        <h2>Interpreting comparisons</h2>
        <p>
          Each evaluation is one stochastic run. Sharing an environment seed does not guarantee
          identical transitions after different actions. A single result cannot establish a general
          winner. The horizon counts model decisions, not treatment days.
        </p>
        <p>
          See the{' '}
          <a
            href={`${REPOSITORY_URL}/blob/main/docs/scientific-model.md`}
            target="_blank"
            rel="noreferrer noopener"
          >
            scientific model specification
          </a>{' '}
          for the full definitions and assumptions.
        </p>
      </section>
    </PublicPage>
  )
}
