import { PublicPage } from './PublicPage'

export function PrivacyPage() {
  return (
    <PublicPage title="Privacy" lede="What is stored when you sign in and run simulations.">
      <section>
        <h2>What the server stores</h2>
        <ul>
          <li>An identifier for your Google account, used only to keep your experiments separate from other people&apos;s.</li>
          <li>Each experiment you run: the starting profile, seeds, and the returned results.</li>
        </ul>
        <p>Your name, email address and picture come from Google for display and are kept in your session cookie, not in the database.</p>
      </section>
      <section>
        <h2>Cookies</h2>
        <ul>
          <li>
            <code>amr.session</code>: your signed-in session. It cannot be read by scripts and ends after a fixed time.
          </li>
          <li>
            <code>amr.csrf</code>: protects state-changing requests from other sites.
          </li>
        </ul>
        <p>There are no advertising or analytics cookies.</p>
      </section>
      <section>
        <h2>What is not collected</h2>
        <p>
          No patient data, no clinical records and no health information. The simulation uses abstract resistance profiles
          only.
        </p>
      </section>
      <section>
        <h2>Deleting your data</h2>
        <p>
          There is no self-service deletion yet. This is a research prototype; ask the project maintainers through the
          repository to remove your stored experiments.
        </p>
      </section>
    </PublicPage>
  )
}
