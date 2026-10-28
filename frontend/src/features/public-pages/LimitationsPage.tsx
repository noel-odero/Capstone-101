import { FiCheck, FiMinus, FiInfo, FiDatabase, FiShuffle, FiBox } from 'react-icons/fi'
import { Link } from 'react-router'
import { GLOSSARY, PROTOTYPE_STATEMENT } from '@/domain/terminology'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function LimitationsPage() {
  return (
    <PublicPage
      title="Understand the boundaries."
      eyebrow="Scope & limitations"
      lede="Useful research starts with knowing what the model represents—and where its evidence ends."
      visual={
        <div className={styles.scopeVisual}>
          <div className={styles.scopeGroup}>
            <span className={styles.eyebrow}>Represented</span>
            {[
              'Binary resistance states',
              'Policy-selected actions',
              'Modeled resistance transitions',
            ].map((text) => (
              <p key={text}>
                <FiCheck aria-hidden="true" />
                {text}
              </p>
            ))}
          </div>
          <div className={styles.scopeGroup}>
            <span className={styles.eyebrow}>Outside the model</span>
            {[
              'Patient-specific response',
              'Bacterial clearance or growth',
              'Dose, duration & clinical efficacy',
            ].map((text) => (
              <p key={text}>
                <FiMinus aria-hidden="true" />
                {text}
              </p>
            ))}
          </div>
        </div>
      }
    >
      <div className={styles.scopeNotice} role="note">
        <FiInfo aria-hidden="true" />
        <p>{PROTOTYPE_STATEMENT} Do not use it to choose antibiotics for a patient.</p>
      </div>
      <section aria-labelledby="limits-title">
        <div className={styles.sectionHeading}>
          <h2 id="limits-title">Keep these three limits in view</h2>
          <span>Before interpreting any result</span>
        </div>
        <div className={styles.threeColumns}>
          {[
            {
              icon: FiDatabase,
              title: 'Incomplete evidence',
              text: 'Some eligible actions have no candidate transition data. The model keeps the state unchanged on those steps.',
              note: 'Unchanged ≠ proven stable',
            },
            {
              icon: FiShuffle,
              title: 'Stochastic outcomes',
              text: 'A single evaluation is one sampled trajectory. It cannot establish that a strategy is better in general.',
              note: 'One run ≠ a general finding',
            },
            {
              icon: FiBox,
              title: 'Simplified biology',
              text: 'Seven binary flags, up to eight steps, and one transition-data scenario cannot describe a whole infection.',
              note: 'Model state ≠ clinical response',
            },
          ].map(({ icon: Icon, title, text, note }) => (
            <div className={styles.limitCard} key={title}>
              <Icon aria-hidden="true" />
              <h3>{title}</h3>
              <p>{text}</p>
              <strong>{note}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className={styles.distinction} aria-labelledby="interpret-limits">
        <div>
          <p className={styles.eyebrow}>Interpret responsibly</p>
          <h2 id="interpret-limits">A result is a starting point for investigation.</h2>
          <p>
            Inspect support gaps and repeat evaluations before drawing conclusions about the
            policies.
          </p>
          <Link className={styles.inlineLink} to="/methodology">
            How the evaluation works
          </Link>
        </div>
        <div className={styles.accordionGroup}>
          {[
            [
              'Susceptibility and action selection',
              'Susceptibility is a binary model flag, not clinical efficacy. All strategies use the same susceptible-action mask. The random baseline samples uniformly; it is neither exhaustive nor optimal.',
            ],
            [
              'Seeds and repeated evaluations',
              GLOSSARY.sameSeed +
                ' Repeated runs help characterize variation; one run is not a significance test or evidence about real patients.',
            ],
            [
              'Biological processes left out',
              'The model omits selected-drug self-resistance, population size, bacterial clearance, dosing, and a policy-controlled stopping decision. Repeated selections and low burden do not establish clinical suitability.',
            ],
            [
              'The 3D illustration',
              'The urinary-tract scene is an aesthetic illustration. It is not a measured or modeled view of infection, bacterial evolution, or treatment response.',
            ],
          ].map(([title, text]) => (
            <details className={styles.details} key={title}>
              <summary>{title}</summary>
              <div className={styles.detailsBody}>
                <p>{text}</p>
              </div>
            </details>
          ))}
        </div>
      </section>
    </PublicPage>
  )
}
