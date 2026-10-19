import { isRouteErrorResponse, useRouteError } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'

/** Last-resort screen for an unexpected rendering failure. The error details stay in the console, not on screen. */
export function RouteError() {
  const error = useRouteError()
  if (!isRouteErrorResponse(error)) {
    console.error(error)
  }
  return (
    <ContentContainer>
      <PageHeader title="Something went wrong" />
      <EmptyState
        title="This page could not be displayed"
        description="An unexpected error stopped the page from rendering. Return to the overview and try again."
        action={<ButtonLink to="/">Go to the overview</ButtonLink>}
      />
    </ContentContainer>
  )
}
