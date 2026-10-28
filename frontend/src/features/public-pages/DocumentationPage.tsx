import { Link } from 'react-router'
import { REPOSITORY_URL } from '@/config/navigation'
import { PublicPage } from './PublicPage'
import styles from './public-pages.module.css'

export function DocumentationPage() {
  const blob = (path: string) => `${REPOSITORY_URL}/blob/main/${path}`
  return (
    <PublicPage title="Documentation" lede="Getting started and finding the technical reference.">
      <section>
        <h2>Getting started</h2>
        <ol>
          <li>Create an account and verify your email using the code sent to your inbox.</li>
          <li>Record a labeled sample or configure a starting resistance profile.</li>
          <li>
            Run a strategy evaluation and inspect the sequences and transitions in Analysis Results.
          </li>
          <li>Reopen saved runs in Analysis History or compare patterns in Analysis Insights.</li>
        </ol>
        <p>
          <Link to="/app">Open the workspace</Link>
        </p>
      </section>
      <section>
        <h2>Technical reference</h2>
        <dl className={styles.definitions}>
          {(
            [
              [
                'README.md',
                'Setup and project overview',
                'Prerequisites, project structure, and local startup commands.',
              ],
              [
                'docs/api.md',
                'API and architecture',
                'Service boundaries, endpoints, and data contracts.',
              ],
              [
                'docs/scientific-model.md',
                'Scientific model',
                'Resistance states, transition rules, and metric definitions.',
              ],
              [
                'docs/research.md',
                'Research and retraining',
                'Training protocols, benchmarks, and frozen model artifacts.',
              ],
              [
                'docs/deployment.md',
                'Deployment',
                'Azure hosting, configuration, backups, and automatic updates.',
              ],
            ] as const
          ).map(([path, title, description]) => (
            <div key={path}>
              <dt>
                <a href={blob(path)} target="_blank" rel="noreferrer noopener">
                  {title}
                </a>
              </dt>
              <dd>{description}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section>
        <h2>Running locally</h2>
        <p>
          Start PostgreSQL and apply migrations, then start the Python service, the .NET API, and
          the frontend, in that order. The API does not apply migrations automatically.
        </p>
        <p>
          Run <code>npm run dev</code> from <code>frontend/</code> for the interface and its API
          proxy. Follow the README for the complete commands and required configuration.
        </p>
      </section>
    </PublicPage>
  )
}
