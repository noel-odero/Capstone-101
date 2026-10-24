import { Link } from 'react-router'
import { REPOSITORY_URL, SIGN_IN_PATH } from '@/config/navigation'
import { APP_NAME } from '@/domain/terminology'
import { Brand } from './Brand'
import { ContentContainer } from './ContentContainer'
import styles from './layout.module.css'

export function PublicFooter({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <footer className={styles.compactFooter}>
        <p>Model-based research only.</p>
        <nav aria-label="Footer resources">
          <Link to="/methodology">Methodology</Link>
          <Link to="/limitations">Limitations</Link>
          <Link to="/privacy">Privacy</Link>
          <a href={REPOSITORY_URL} rel="noreferrer noopener" target="_blank">
            Source
          </a>
        </nav>
      </footer>
    )
  }
  return (
    <footer className={styles['footer']}>
      <ContentContainer>
        <div className={styles['footerGrid']}>
          <div>
            <Brand />
            <p className={styles['footerBlurb']} style={{ marginTop: 'var(--space-3)' }}>
              An AI-powered antibiotic strategy evaluation platform for model-based research.
            </p>
          </div>
          <nav className={styles['footerColumn']} aria-labelledby="footer-learn">
            <h2 id="footer-learn">Learn</h2>
            <ul>
              <li>
                <Link to="/about">About</Link>
              </li>
              <li>
                <Link to="/methodology">Methodology</Link>
              </li>
              <li>
                <Link to="/limitations">Limitations</Link>
              </li>
            </ul>
          </nav>
          <nav className={styles['footerColumn']} aria-labelledby="footer-resources">
            <h2 id="footer-resources">Resources</h2>
            <ul>
              <li>
                <Link to="/documentation">Documentation</Link>
              </li>
              <li>
                <a href={REPOSITORY_URL} rel="noreferrer noopener" target="_blank">
                  Source on GitHub
                </a>
              </li>
            </ul>
          </nav>
          <nav className={styles['footerColumn']} aria-labelledby="footer-account">
            <h2 id="footer-account">Account</h2>
            <ul>
              <li>
                <Link to={SIGN_IN_PATH}>Sign in</Link>
              </li>
              <li>
                <Link to="/privacy">Privacy</Link>
              </li>
            </ul>
          </nav>
        </div>
        <p className={styles['footerNote']}>
          {APP_NAME} is a research prototype. Findings are model-derived and are not clinical
          treatment recommendations.
        </p>
      </ContentContainer>
    </footer>
  )
}
