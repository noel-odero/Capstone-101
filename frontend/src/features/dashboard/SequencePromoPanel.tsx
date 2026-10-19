import { ArrowRight } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { ButtonLink } from '@/components/ui/Button'
import { EcoliIllustration } from '@/features/scene/EcoliIllustration'
import styles from './dashboard.module.css'

const EcoliHeroScene = lazy(() => import('@/features/scene/EcoliHeroScene').then((module) => ({ default: module.EcoliHeroScene })))

export function SequencePromoPanel() {
  return (
    <section className={styles['promo']} aria-labelledby="promo-title">
      <div className={styles['promoCopy']}>
        <h2 id="promo-title">See how the sequence changes simulated resistance</h2>
        <p>Run PPO and the random baseline from the same profile and compare them step by step.</p>
        <ButtonLink to="/app/simulation/new" variant="dark">
          Run Simulation <ArrowRight size={16} aria-hidden="true" />
        </ButtonLink>
      </div>
      <div className={styles['promoVisual']}>
        <Suspense fallback={<EcoliIllustration />}>
          <EcoliHeroScene />
        </Suspense>
      </div>
    </section>
  )
}
