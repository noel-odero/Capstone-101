import { PublicPage } from './PublicPage'

export function PrivacyPage() {
  return (
    <PublicPage title="Privacy" lede="What is stored when you sign in and run analyses.">
      <section>
        <h2>What the server stores</h2>
        <ul>
          <li>
            Your account identifier, email address, display name, email-verification status and
            sign-in security records.
          </li>
          <li>
            Samples you save, including their labels, dates added and initial resistance profiles.
          </li>
          <li>
            Your saved analyses and research collections, including resistance profiles, seeds,
            evaluation settings and results.
          </li>
        </ul>
        <p>
          You sign in with your email address and password. Your password is stored as a salted
          hash, not as plain text. Verification emails are sent through Azure Communication Services
          Email.
        </p>
      </section>
      <section>
        <h2>Cookies</h2>
        <ul>
          <li>
            <code>amr.session</code>: your signed-in session. It cannot be read by scripts and ends
            after a fixed time.
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
          No patient data, no clinical records and no health information. The evaluation model uses
          abstract resistance profiles only.
        </p>
      </section>
      <section>
        <h2>Deleting your data</h2>
        <p>
          You can delete samples from the Samples page. Deleting a sample removes it from your
          sample library, but any saved analyses created from it, including their resistance
          profiles and results, remain in Analysis History.
        </p>
        <p>
          Self-service deletion of saved analyses and accounts is not currently available. Contact
          the project maintainer to request their removal.
        </p>
      </section>
    </PublicPage>
  )
}
