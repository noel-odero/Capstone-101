import { useEffect } from 'react'
import { HeroSection } from './HeroSection'
export function LandingPage() {
  useEffect(() => {
    const previousTitle = document.title
    const description = document.querySelector('meta[name="description"]')
    const previousDescription = description?.getAttribute('content')
    document.title = 'StewardLab | Antibiotic stewardship research'
    description?.setAttribute(
      'content',
      'Simulate resistance evolution, compare antibiotic selection strategies, and explore the assumptions behind simulated E. coli resistance outcomes.',
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
