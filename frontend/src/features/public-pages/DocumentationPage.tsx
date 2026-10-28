import { FiBookOpen, FiCode, FiCpu, FiExternalLink, FiServer } from 'react-icons/fi'
import { Link } from 'react-router'
import { REPOSITORY_URL } from '@/config/navigation'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function DocumentationPage() {
  const blob = (path: string) => `${REPOSITORY_URL}/blob/main/${path}`
  return (
    <PublicPage
      title="A place to start. A reference to return to."
      eyebrow="Documentation"
      lede="Get your first analysis running, then go deeper into the platform and its research model."
      visual={
        <figure className={styles.previewVisual}>
          <div className={styles.visualLabel}>
            <span>Your research workspace</span>
            <span className={styles.statusDot} aria-hidden="true" />
          </div>
          <img
            src="/images/workbench-preview.png"
            alt="Workbench preview with a 3D urinary-tract illustration, resistance trajectories and strategy metrics"
          />
          <figcaption>Configure. Evaluate. Inspect.</figcaption>
        </figure>
      }
    >
      <section aria-labelledby="getting-started">
        <div className={styles.sectionHeading}>
          <h2 id="getting-started">Your first investigation</h2>
          <Link to="/app">Open workspace</Link>
        </div>
        <ol className={styles.quickStart}>
          {[
            [
              'Create your account',
              'Sign up with an email and password. Enter the verification code from your inbox.',
            ],
            [
              'Choose a starting state',
              'Record a labeled sample or configure the seven-antibiotic resistance profile.',
            ],
            [
              'Evaluate and inspect',
              'Compare PPO, DQN, and the baseline. Open Analysis Results to review decisions and transitions.',
            ],
            [
              'Return to the evidence',
              'Find saved runs in Analysis History. Explore patterns across them in Analysis Insights.',
            ],
          ].map(([title, text], index) => (
            <li key={title}>
              <span className={styles.stepNumber}>0{index + 1}</span>
              <div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <section aria-labelledby="reference-title">
        <div className={styles.sectionHeading}>
          <h2 id="reference-title">Go deeper</h2>
          <span>Reference documents on GitHub</span>
        </div>
        <div className={styles.twoColumns}>
          {[
            {
              icon: FiBookOpen,
              title: 'Setup & overview',
              text: 'Project structure, prerequisites, and local startup.',
              path: 'README.md',
              label: 'Start here',
            },
            {
              icon: FiCode,
              title: 'API & architecture',
              text: 'Service boundaries, endpoints, and data contracts.',
              path: 'docs/api.md',
              label: 'Development',
            },
            {
              icon: FiCpu,
              title: 'Scientific model',
              text: 'State encoding, transition rules, and metric definitions.',
              path: 'docs/scientific-model.md',
              label: 'Model reference',
            },
            {
              icon: FiServer,
              title: 'Research & retraining',
              text: 'Training protocols, benchmarks, and frozen artifacts.',
              path: 'docs/research.md',
              label: 'Research',
            },
          ].map(({ icon: Icon, title, text, path, label }) => (
            <a
              className={styles.resourceLink}
              href={blob(path)}
              key={path}
              target="_blank"
              rel="noreferrer noopener"
            >
              <Icon aria-hidden="true" />
              <div>
                <span className={styles.caption}>{label}</span>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
              <FiExternalLink aria-hidden="true" />
            </a>
          ))}
        </div>
      </section>
      <details className={styles.details}>
        <summary>Running the platform locally</summary>
        <div className={styles.detailsBody}>
          <div className={styles.serviceChain}>
            <span>PostgreSQL</span>
            <span>Python model service</span>
            <span>.NET API</span>
            <span>React frontend</span>
          </div>
          <p>
            Start services in that order. Apply database migrations before starting the API; it
            never changes the schema automatically. Run <code>npm run dev</code> in{' '}
            <code>frontend/</code> for the interface and its API proxy.
          </p>
          <p>
            Sessions use cookies, and protected requests carry a CSRF token. Email verification
            requires the configured email service.
          </p>
          <a
            className={styles.inlineLink}
            href={blob('README.md')}
            target="_blank"
            rel="noreferrer noopener"
          >
            Full setup instructions <FiExternalLink aria-hidden="true" />
          </a>
        </div>
      </details>
    </PublicPage>
  )
}
