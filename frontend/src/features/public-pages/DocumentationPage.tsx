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
          Running simulations needs a signed-in user. Google sign-in is configured on the server
          with these environment variables; they are never part of the interface.
        </p>
        <pre>{`Auth__Google__ClientId
Auth__Google__ClientSecret`}</pre>
        <p>
          The authorized redirect URI in Google Cloud must be the API&apos;s callback, for example{' '}
          <code>http://localhost:5173/api/v1/auth/google/callback</code> in development.
        </p>
      </section>
      <section>
        <h2>Documents</h2>
        <ul>
          <li>
            <a href={blob('backend/README.md')} rel="noreferrer noopener" target="_blank">
              Backend README
            </a>
          </li>
          <li>
            <a
              href={blob('backend/docs/api-contract.md')}
              rel="noreferrer noopener"
              target="_blank"
            >
              API contract
            </a>
          </li>
          <li>
            <a href={blob('service/README.md')} rel="noreferrer noopener" target="_blank">
              Python service README
            </a>
          </li>
          <li>
            <a href={blob('README.md')} rel="noreferrer noopener" target="_blank">
              Project README
            </a>
          </li>
        </ul>
      </section>
    </PublicPage>
  )
}
