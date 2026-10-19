import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'

export function NotFoundPage() {
  return (
    <ContentContainer>
      <PageHeader title="Page not found" />
      <EmptyState
        title="There is nothing at this address"
        description="Check the link, or go back to the start."
        action={<ButtonLink to="/">Go to the start</ButtonLink>}
      />
    </ContentContainer>
  )
}
