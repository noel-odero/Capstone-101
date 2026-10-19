import { ContentContainer } from '@/components/layout/ContentContainer'
import { STRATEGY_DESCRIPTIONS, STRATEGY_NAMES } from '@/domain/terminology'
import styles from './landing.module.css'

const STEPS = [
  { title: 'Choose a profile', text: 'Mark each of the seven antibiotics susceptible or resistant.' },
  { title: 'Run both strategies', text: 'PPO and a random baseline each act for eight steps.' },
  { title: 'Inspect every step', text: 'See the action, its transition support and the outcome.' },
] as const

export function HowItWorksSection() {
  return (
    <ContentContainer>
      <section id="how-it-works" className={styles['section']} aria-labelledby="how-title">
        <div className={styles['sectionHead']}>
          <h2 id="how-title">How it works</h2>
        </div>
        <ol className={styles['steps']}>
          {STEPS.map((step, index) => (
            <li key={step.title} className={styles['step']}>
              <span className={styles['stepNumber']} aria-hidden="true">
                {index + 1}
              </span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </section>
      <section className={styles['section']} style={{ paddingTop: 0 }} aria-labelledby="versus-title">
        <div className={styles['sectionHead']}>
          <h2 id="versus-title">PPO versus the Random Susceptible Baseline</h2>
        </div>
        <div className={styles['versus']}>
          <div className={`${styles['strategy']} ${styles['strategyPpo']}`}>
            <h3>{STRATEGY_NAMES.ppo}</h3>
            <p>{STRATEGY_DESCRIPTIONS.ppo}</p>
          </div>
          <div className={`${styles['strategy']} ${styles['strategyBaseline']}`}>
            <h3>{STRATEGY_NAMES.random_susceptible_baseline}</h3>
            <p>{STRATEGY_DESCRIPTIONS.random_susceptible_baseline}</p>
          </div>
        </div>
      </section>
    </ContentContainer>
  )
}
