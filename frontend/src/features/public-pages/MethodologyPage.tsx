import { FiFilter, FiGitBranch, FiRepeat, FiExternalLink } from 'react-icons/fi'
import { REPOSITORY_URL } from '@/config/navigation'
import { GLOSSARY } from '@/domain/terminology'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function MethodologyPage() {
  return (
    <PublicPage
      title="Follow the decision. Inspect the change."
      eyebrow="Methodology"
      lede="One starting profile. Three strategies. A traceable sequence of model-derived outcomes."
      visual={
        <figure className={styles.processVisual}>
          <div className={styles.visualLabel}>
            <span>Inside an evaluation</span>
            <FiRepeat aria-hidden="true" />
          </div>
          <div className={styles.processNode}>
            <span>01</span>
            <div>
              <strong>Resistance state</strong>
              <small>7 susceptible / resistant flags</small>
            </div>
          </div>
          <div className={styles.processNode}>
            <span>02</span>
            <div>
              <strong>Eligible action</strong>
              <small>Policy chooses a susceptible antibiotic</small>
            </div>
          </div>
          <div className={styles.processNode}>
            <span>03</span>
            <div>
              <strong>Next state</strong>
              <small>Sample from candidate transitions</small>
            </div>
          </div>
          <figcaption>
            Repeat for up to 8 steps, or stop when no susceptible action remains.
          </figcaption>
        </figure>
      }
    >
      <section aria-labelledby="strategies-title">
        <div className={styles.sectionHeading}>
          <h2 id="strategies-title">Same environment. Different decisions.</h2>
          <span>All three use the same action mask</span>
        </div>
        <div className={styles.threeColumns}>
          {[
            {
              name: 'PPO',
              type: 'Proximal Policy Optimization',
              text: 'A frozen learned policy selects an eligible antibiotic at each step.',
              color: 'var(--color-series-ppo)',
            },
            {
              name: 'DQN',
              type: 'Deep Q-Network',
              text: 'A frozen value-based policy selects from the same eligible actions.',
              color: 'var(--color-series-dqn)',
            },
            {
              name: 'Random baseline',
              type: 'Susceptible-action reference',
              text: 'Samples uniformly among eligible antibiotics. It does not search for the best sequence.',
              color: 'var(--color-series-baseline)',
            },
          ].map(({ name, type, text, color }) => (
            <div className={styles.strategy} key={name} style={{ borderTopColor: color }}>
              <span className={styles.strategyDot} style={{ background: color }} />
              <h3>{name}</h3>
              <span className={styles.caption}>{type}</span>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>
      <section className={styles.distinction} aria-labelledby="interpret-title">
        <div>
          <p className={styles.eyebrow}>Reading a result</p>
          <h2 id="interpret-title">Three separate questions</h2>
          <p>
            An eligible action can still lack transition data. An unchanged state does not prove
            effectiveness.
          </p>
        </div>
        <div className={styles.questionList}>
          <div>
            <FiFilter aria-hidden="true" />
            <div>
              <h3>Can it be selected?</h3>
              <p>Only antibiotics marked susceptible are eligible.</p>
            </div>
          </div>
          <div>
            <FiGitBranch aria-hidden="true" />
            <div>
              <h3>Is a transition supported?</h3>
              <p>Candidate data must exist for this action and state.</p>
            </div>
          </div>
          <div>
            <FiRepeat aria-hidden="true" />
            <div>
              <h3>What changed?</h3>
              <p>The engine samples an outcome. Without support, the profile stays unchanged.</p>
            </div>
          </div>
        </div>
      </section>
      <section aria-labelledby="metrics-title">
        <div className={styles.sectionHeading}>
          <h2 id="metrics-title">Read the metrics independently</h2>
          <span>No automatic winner</span>
        </div>
        <div className={styles.twoColumns}>
          {[
            [
              'Resistance burden',
              'Lower',
              'Sum of resistant-drug fractions across steps. All-resistant states are charged for the remaining horizon.',
            ],
            ['Resistance emergence', 'Lower', GLOSSARY.resistanceEmergence],
            [
              'Susceptible options',
              'Higher',
              'Antibiotics still marked susceptible at the end of the evaluation.',
            ],
            [
              'Susceptible-action rate',
              'Mask check',
              'The mask makes this 1.0 for all strategies that act. It does not measure treatment effectiveness.',
            ],
          ].map(([title, direction, text]) => (
            <div className={styles.metricDefinition} key={title}>
              <div>
                <h3>{title}</h3>
                <span className={styles.tag}>{direction}</span>
              </div>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>
      <details className={styles.details}>
        <summary>Evaluation assumptions and full specification</summary>
        <div className={styles.detailsBody}>
          <p>
            Results are computational outcomes, not patient measurements. Policies remain frozen
            during evaluation. {GLOSSARY.sameSeed}
          </p>
          <p>
            The horizon counts model decisions, not treatment days. The baseline is implemented by
            the class named Greedy in the scientific code.
          </p>
          <a
            className={styles.inlineLink}
            href={`${REPOSITORY_URL}/blob/main/docs/scientific-model.md`}
            target="_blank"
            rel="noreferrer noopener"
          >
            Read the scientific model <FiExternalLink aria-hidden="true" />
          </a>
        </div>
      </details>
    </PublicPage>
  )
}
