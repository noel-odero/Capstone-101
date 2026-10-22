import { ScientificLimitationsNotice } from '@/components/scientific/ScientificLimitationsNotice'
import { PublicPage } from './PublicPage'

export function LimitationsPage() {
  return (
    <PublicPage title="Limitations" lede="What these results can and cannot tell you.">
      <ScientificLimitationsNotice detailed />
    </PublicPage>
  )
}
