import { Link } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { REPOSITORY_URL } from '@/config/navigation'
import { CapabilitiesSection } from './CapabilitiesSection'
import { HeroSection } from './HeroSection'
import { HowItWorksSection } from './HowItWorksSection'
import { LandingVisualizationPreview } from './LandingVisualizationPreview'
import { ResearchProblemSection } from './ResearchProblemSection'
import styles from './landing.module.css'

export function LandingPage() {
  return (
    <>
      <HeroSection />
      <CapabilitiesSection />
      <ResearchProblemSection />
      <HowItWorksSection />
      <LandingVisualizationPreview />
      <ContentContainer>
        <section className={styles['limits']} aria-labelledby="limits-title">
          <h2 id="limits-title">Scope and limits</h2>
          <ul>
            <li>A simplified simulation: seven antibiotics, binary resistance, a fixed eight-step horizon.</li>
            <li>Susceptible means susceptible in the simulation. It is not clinical efficacy.</li>
            <li>Not clinically validated. Not for choosing treatment for anyone.</li>
          </ul>
          <div className={styles['links']}>
            <Link to="/limitations">Read the limitations</Link>
            <Link to="/methodology">Methodology</Link>
            <Link to="/documentation">Documentation</Link>
            <a href={REPOSITORY_URL} rel="noreferrer noopener" target="_blank">
              Source on GitHub
            </a>
          </div>
        </section>
      </ContentContainer>
    </>
  )
}
