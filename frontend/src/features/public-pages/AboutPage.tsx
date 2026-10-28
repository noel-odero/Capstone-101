import { FiArchive, FiLayers, FiActivity, FiGithub } from 'react-icons/fi'
import { Link } from 'react-router'
import { REPOSITORY_URL } from '@/config/navigation'
import { PROTOTYPE_STATEMENT } from '@/domain/terminology'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function AboutPage() {
  return (
    <PublicPage
      title="Better questions. Clearer evidence."
      eyebrow="About StewardLab"
      lede="A research workspace for exploring how antibiotic choices shape modeled E. coli resistance."
      visual={
        <figure className={styles.stateVisual}>
          <div className={styles.visualLabel}>
            <span>The model at a glance</span>
            <FiLayers aria-hidden="true" />
          </div>
          <div className={styles.stateGrid} aria-hidden="true">
            {Array.from({ length: 128 }, (_, state) => (
              <span
                key={state}
                style={{ opacity: 0.2 + state.toString(2).replaceAll('0', '').length / 9 }}
              />
            ))}
          </div>
          <div className={styles.modelNumbers}>
            <div>
              <strong>128</strong>
              <span>possible states</span>
            </div>
            <div>
              <strong>7</strong>
              <span>antibiotics</span>
            </div>
            <div>
              <strong>3</strong>
              <span>strategies</span>
            </div>
          </div>
          <figcaption>
            Shade indicates resistant-drug count. These are model states, not measured isolates.
          </figcaption>
        </figure>
      }
    >
      <section className={styles.question}>
        <p className={styles.eyebrow}>The research question</p>
        <h2>Can a learned strategy preserve more susceptible options?</h2>
        <p>
          Compare frozen PPO and DQN policies with a random susceptible-action baseline, under the
          same starting conditions.
        </p>
      </section>
      <section aria-labelledby="about-workflow">
        <div className={styles.sectionHeading}>
          <h2 id="about-workflow">From a profile to an investigation</h2>
          <span>Built for researchers and students</span>
        </div>
        <div className={styles.threeColumns}>
          {[
            {
              icon: FiArchive,
              title: 'Record',
              text: 'Keep labeled sample profiles together and track what needs evaluation.',
            },
            {
              icon: FiActivity,
              title: 'Compare',
              text: 'Inspect strategy outcomes, resistance changes, and transition evidence.',
            },
            {
              icon: FiLayers,
              title: 'Investigate',
              text: 'Revisit saved analyses and find questions worth exploring next.',
            },
          ].map(({ icon: Icon, title, text }, index) => (
            <div className={styles.feature} key={title}>
              <div className={styles.featureTop}>
                <Icon aria-hidden="true" />
                <span>0{index + 1}</span>
              </div>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>
      <div className={styles.bottomBar}>
        <div>
          <strong>Explore with the assumptions in view.</strong>
          <p>{PROTOTYPE_STATEMENT}</p>
        </div>
        <Link className={styles.actionLink} to="/methodology">
          See the methodology
        </Link>
      </div>
      <details className={styles.details}>
        <summary>Under the hood</summary>
        <div className={styles.detailsBody}>
          <p>
            React interface · ASP.NET Core API · PostgreSQL storage · Python evaluation engine. PPO
            and DQN are trained offline and frozen during analysis.
          </p>
          <a
            className={styles.inlineLink}
            href={REPOSITORY_URL}
            target="_blank"
            rel="noreferrer noopener"
          >
            <FiGithub aria-hidden="true" /> Explore the source
          </a>
        </div>
      </details>
    </PublicPage>
  )
}
