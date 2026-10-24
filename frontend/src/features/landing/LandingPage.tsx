import { useEffect } from 'react'
import { HeroSection } from './HeroSection'
import { APP_NAME, APP_TAGLINE } from '@/domain/terminology'
export function LandingPage() {
  useEffect(() => {
    const previousTitle = document.title
    const description = document.querySelector('meta[name="description"]')
    const previousDescription = description?.getAttribute('content')
    document.title = `${APP_NAME} | Antibiotic strategy evaluation`
    description?.setAttribute(
      'content',
      `${APP_NAME}: ${APP_TAGLINE} Compare PPO, DQN and baseline policies in a model-based research environment. Not for clinical prescribing.`,
    )
    return () => {
      document.title = previousTitle
      if (previousDescription != null) description?.setAttribute('content', previousDescription)
    }
  }, [])
  return (
    <>
      <HeroSection />
    </>
  )
}
