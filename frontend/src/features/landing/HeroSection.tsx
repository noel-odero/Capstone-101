import { Play } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { ButtonLink } from '@/components/ui/Button'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { EcoliIllustration } from '@/features/scene/EcoliIllustration'
import { SIGN_IN_PATH, WORKSPACE_PATH } from '@/config/navigation'
import { APP_NAME, APP_SUBTITLE } from '@/domain/terminology'
import { useAuth } from '@/features/auth/useAuth'
import styles from './landing.module.css'

const EcoliHeroScene = lazy(() => import('@/features/scene/EcoliHeroScene').then((module) => ({ default: module.EcoliHeroScene })))

export function HeroSection() {
  const auth = useAuth()
  const destination = auth.status === 'authenticated' ? WORKSPACE_PATH : `${SIGN_IN_PATH}?returnTo=${encodeURIComponent(WORKSPACE_PATH)}`

  return (
    <section className={styles['hero']} aria-labelledby="hero-title">
      <ContentContainer>
        <div className={styles['heroGrid']}>
          <div className={styles['heroCopy']}>
            <span className={styles['eyebrow']}>{APP_NAME} &middot; Research prototype</span>
            <h1 id="hero-title" className={styles['headline']}>
              Explore how antibiotic sequences shape simulated resistance
            </h1>
            <p className={styles['lede']}>
              {APP_SUBTITLE} Compare a trained PPO policy with a random baseline and follow every step.
            </p>
            <div className={styles['actions']}>
              <ButtonLink to={destination}>
                <Play size={16} aria-hidden="true" /> Explore the Simulation
              </ButtonLink>
              <ButtonLink to="#how-it-works" variant="secondary">
                How It Works
              </ButtonLink>
            </div>
          </div>
          <div className={styles['heroVisual']}>
            <Suspense fallback={<EcoliIllustration />}>
              <EcoliHeroScene />
            </Suspense>
          </div>
        </div>
      </ContentContainer>
    </section>
  )
}
