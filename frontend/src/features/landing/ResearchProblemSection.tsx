import { ContentContainer } from '@/components/layout/ContentContainer'
import styles from './landing.module.css'

export function ResearchProblemSection() {
  return (
    <ContentContainer>
      <section className={styles['section']} aria-labelledby="problem-title">
        <div className={styles['sectionHead']}>
          <h2 id="problem-title">The research problem</h2>
          <p>
            Choosing an antibiotic is not only about today. Each choice can change which antibiotics stay susceptible later.
            This prototype studies that sequence in a simulation of <em>E. coli</em> resistance to seven antibiotics.
          </p>
        </div>
      </section>
    </ContentContainer>
  )
}
