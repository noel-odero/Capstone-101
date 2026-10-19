import { ContentContainer } from '@/components/layout/ContentContainer'
import { SequenceMatrix } from '@/components/scientific/SequenceMatrix'
import { parseProfileCode } from '@/domain/profile'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import type { ResistanceProfile } from '@/domain/types'
import styles from './landing.module.css'

/** ILLUSTRATIVE ONLY: invented to show how the matrix reads. It is not model output and is labelled as such on screen. */
const ILLUSTRATIVE_CODES = [
  '0100000',
  '0100000',
  '0100000',
  '0100100',
  '0100100',
  '1100100',
  '1100100',
  '1101100',
  '1101110',
] as const

const ILLUSTRATIVE_PROFILES = ILLUSTRATIVE_CODES.map((code) => parseProfileCode(code)).filter(
  (profile): profile is ResistanceProfile => profile !== null,
)

export function LandingVisualizationPreview() {
  const antibiotics = useAntibiotics()

  return (
    <ContentContainer>
      <section className={`${styles['section']} ${styles['preview']}`} aria-labelledby="preview-title">
        <div className={styles['sectionHead']} style={{ marginBottom: 0 }}>
          <h2 id="preview-title">See resistance change, step by step</h2>
          <p>
            Every run is shown as a grid of the seven antibiotics across eight steps, next to a 3D view of the same state. This
            sample is only a drawing of the layout.
          </p>
        </div>
        {antibiotics.data ? (
          <SequenceMatrix
            caption="Resistance trajectory"
            tag="Illustrative demo data"
            entries={antibiotics.data}
            profiles={ILLUSTRATIVE_PROFILES}
            selectedStep={4}
          />
        ) : (
          <p className="muted" role="status">
            {antibiotics.isPending ? 'Loading the preview' : 'The preview needs the API, which is not reachable right now.'}
          </p>
        )}
      </section>
    </ContentContainer>
  )
}
