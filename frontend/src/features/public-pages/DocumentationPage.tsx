import { REPOSITORY_URL } from '@/config/navigation'
import { PublicPage } from './PublicPage'

export function DocumentationPage() {
  const blob = (path: string) => `${REPOSITORY_URL}/blob/main/${path}`
  return (
    <PublicPage
      title="Documentation"
      lede="Run the project locally and find the detailed documents."
    >
      <section>
        <h2>Run it locally</h2>
        <ol>
          <li>
            Start PostgreSQL and apply the migrations (the API never changes the schema on its own).
          </li>
          <li>Start the Python service, then the ASP.NET Core API.</li>
          <li>
            Start this interface with <code>npm run dev</code> in <code>frontend/</code>. It proxies{' '}
            <code>/api</code> to the API.
          </li>
        </ol>
      </section>
      <section>
        <h2>Sign-in</h2>
        <p>
          Create an account with your email and password to save samples and run analyses. Sessions
          use cookies; the interface includes the session&apos;s CSRF token with protected requests.
        </p>
      </section>
      <section>
        <h2>Documents</h2>
        <ul>
          <li>
            <a href={blob('README.md')} rel="noreferrer noopener" target="_blank">
              Setup and project overview
            </a>
          </li>
          <li>
            <a
              href={blob('docs/api.md')}
              rel="noreferrer noopener"
              target="_blank"
            >
              API and architecture
            </a>
          </li>
          <li>
            <a href={blob('docs/scientific-model.md')} rel="noreferrer noopener" target="_blank">
              Scientific model
            </a>
          </li>
          <li>
            <a href={blob('docs/research.md')} rel="noreferrer noopener" target="_blank">
              Research and retraining
            </a>
          </li>
        </ul>
      </section>
    </PublicPage>
  )
}
