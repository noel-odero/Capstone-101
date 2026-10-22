import { useParams } from 'react-router'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { useAntibiotics } from '@/hooks/useAntibiotics'
import { useComparison } from '@/hooks/useComparison'
import { useSimulation } from '@/hooks/useSimulation'
import { ResultsWorkbench } from './ResultsWorkbench'

export function RecommendationPage() {
  const { comparisonId, simulationId } = useParams()
  const comparison = useComparison(comparisonId)
  const simulation = useSimulation(simulationId)
  const antibiotics = useAntibiotics()
  const query = comparisonId ? comparison : simulation
  const run = query.data
  const ppo = run && ('ppo' in run ? run.ppo : run.result)
  const baseline = run && 'baseline' in run ? run.baseline : null
  return (
    <ContentContainer>
      {query.isPending || antibiotics.isPending ? (
        <>
          <PageHeader title="Results and Recommendations" />
          <LoadingState label="Loading simulation results" lines={3} block />
        </>
      ) : query.isError || antibiotics.isError ? (
        <>
          <PageHeader title="Results and Recommendations" />
          <ErrorState
            error={query.error ?? antibiotics.error}
            onRetry={() => {
              void query.refetch()
              void antibiotics.refetch()
            }}
          />
        </>
      ) : run?.status === 'completed' && ppo && antibiotics.data ? (
        <ResultsWorkbench
          key={run.id}
          run={run}
          ppo={ppo}
          baseline={baseline ?? null}
          antibiotics={antibiotics.data}
          comparisonId={comparisonId}
        />
      ) : (
        <>
          <PageHeader title="Results and Recommendations" />
          <EmptyState
            title="No completed results available"
            description="Choose a completed run or configure a new simulation."
            action={<ButtonLink to="/app/history">Open history</ButtonLink>}
          />
        </>
      )}
    </ContentContainer>
  )
}
