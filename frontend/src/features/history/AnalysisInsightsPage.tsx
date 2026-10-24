import { useEffect, useRef, useState } from 'react'
import { Navigate, Link, useSearchParams } from 'react-router'
import { FiActivity, FiBookOpen, FiDownload, FiFilter, FiFolder, FiSearch } from 'react-icons/fi'
import { ContentContainer } from '@/components/layout/ContentContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button, ButtonLink } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { AnalysisInspector } from './AnalysisInspector'
import { InsightCharts } from './InsightCharts'
import { InsightCollections } from './InsightCollections'
import { InsightEvidence } from './InsightEvidence'
import { InsightSelection } from './InsightSelection'
import { downloadEvidence, evidenceReport, metricsCsv } from './insight-export'
import {
  matchesInvestigation,
  summarizeEvidence,
  INVESTIGATION_LABELS,
  type Investigation,
} from './insight-data'
import {
  readSelection,
  useAnalysisCollections,
  useAnalysisHistory,
  useHistoryComparison,
  validSelection,
  type AnalysisCollection,
  type HistoryComparison,
  type SavedAnalysis,
} from './history-api'
import styles from './insights.module.css'

type InsightsTab = 'overview' | 'evidence' | 'collections'

export function LegacyInsightsRedirect() {
  const [params] = useSearchParams()
  return <Navigate to={`/app/insights?${params}`} replace />
}

export function AnalysisInsightsPage() {
  const [params, setParams] = useSearchParams()
  const latest = useAnalysisHistory(new URLSearchParams())
  const collections = useAnalysisCollections()
  const ids = readSelection(params.get('ids'))
  const valid = validSelection(params.get('ids'))
  const comparison = useHistoryComparison(ids, valid)
  const requestedTab = params.get('tab')
  const tab: InsightsTab =
    requestedTab === 'evidence' || requestedTab === 'collections' ? requestedTab : 'overview'
  const [picking, setPicking] = useState(false)
  const [inspected, setInspected] = useState<string | null>(null)
  const filter = Object.hasOwn(INVESTIGATION_LABELS, params.get('case') ?? '')
    ? (params.get('case') as Investigation)
    : 'all'
  const profile = params.get('focusProfile') ?? ''
  const collection = collections.data?.find((item) => item.id === params.get('collection'))
  const active = comparison.data?.analyses.find((run) => run.id === inspected)

  useEffect(() => {
    if (params.has('ids') || !latest.data || latest.data.items.length < 2) return
    setParams(
      (previous) => {
        if (previous.has('ids')) return previous
        const next = new URLSearchParams(previous)
        next.set('ids', latest.data.items.map((run) => run.id).join(','))
        return next
      },
      { replace: true },
    )
  }, [latest.data, params, setParams])

  function update(values: Record<string, string>) {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      for (const [key, value] of Object.entries(values)) {
        if (value) next.set(key, value)
        else next.delete(key)
      }
      return next
    })
  }
  function choose() {
    setPicking(true)
    update({ tab: 'evidence' })
  }
  function applySelection(next: string[]) {
    update({ ids: next.join(','), tab: 'overview', case: '', focusProfile: '', collection: '' })
    setPicking(false)
    setInspected(null)
  }
  function openCollection(next: AnalysisCollection) {
    update({
      ids: next.analysisIds.join(','),
      collection: next.id,
      tab: 'overview',
      case: '',
      focusProfile: '',
    })
    setPicking(false)
    setInspected(null)
  }
  return (
    <ContentContainer>
      <PageHeader
        title="Analysis Insights"
        subtitle="Find patterns. Examine uncertainty. Plan the next question."
        action={
          <div className={styles.headerActions}>
            <Button
              variant="secondary"
              size="sm"
              aria-label="Choose analyses for insights"
              onClick={choose}
            >
              <FiFilter aria-hidden="true" />
              Choose analyses
            </Button>
            {comparison.data ? <ExportMenu data={comparison.data} collection={collection} /> : null}
          </div>
        }
      />
      <div className={styles.contextLine}>
        <span>
          {ids.length} selected{latest.data ? ` / ${latest.data.totalCount} saved analyses` : ''}
          {collection ? ` · ${collection.name}` : ''}
        </span>
        <Link to="/app/history">View Analysis History</Link>
      </div>
      <nav className={styles.tabs} aria-label="Insights views">
        {(
          [
            ['overview', 'Overview', FiActivity],
            ['evidence', 'Evidence library', FiBookOpen],
            ['collections', 'Collections', FiFolder],
          ] as const
        ).map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            aria-current={tab === key ? 'page' : undefined}
            onClick={() => {
              update({ tab: key })
              setPicking(false)
            }}
          >
            <Icon aria-hidden="true" />
            {label}
          </button>
        ))}
      </nav>
      <div className={styles.workspace}>
        {collection?.question ? (
          <p className={styles.collectionQuestion}>
            <FiSearch aria-hidden="true" />
            {collection.question}
          </p>
        ) : null}
        {tab === 'collections' ? (
          <InsightCollections ids={valid ? ids : []} onOpen={openCollection} onChoose={choose} />
        ) : (
          <>
            {(latest.isPending && !valid) || (comparison.isPending && valid) ? (
              <LoadingState label="Reading research evidence" lines={4} />
            ) : null}
            {!valid && latest.isError ? (
              <ErrorState error={latest.error} onRetry={() => void latest.refetch()} />
            ) : null}
            {valid && comparison.isError ? (
              <ErrorState
                error={comparison.error}
                title="Selected analyses could not be loaded"
                onRetry={() => void comparison.refetch()}
              >
                <Button variant="secondary" onClick={choose}>
                  Choose other analyses
                </Button>
              </ErrorState>
            ) : null}
            {tab === 'evidence' && picking ? (
              <InsightSelection
                key={ids.join(',')}
                ids={ids}
                onApply={applySelection}
                onCancel={() => setPicking(false)}
              />
            ) : null}
            {!valid && !latest.isPending && !picking ? (
              <EmptyState
                title="Start with a research question"
                description="Choose 2–50 saved analyses to investigate. You can compare existing records without running the models again."
                action={
                  <div className="row">
                    <Button onClick={choose}>Choose analyses</Button>
                    <ButtonLink variant="secondary" to="/app/simulation/new">
                      New Analysis
                    </ButtonLink>
                  </div>
                }
              />
            ) : null}
            {comparison.data && valid && !picking ? (
              <>
                <Compatibility data={comparison.data} />
                {tab === 'overview' ? (
                  <>
                    <InsightsOverview
                      data={comparison.data}
                      onInspect={setInspected}
                      onInvestigate={(next, nextProfile = '') =>
                        update({ case: next, focusProfile: nextProfile, tab: 'evidence' })
                      }
                    />
                  </>
                ) : (
                  <InsightEvidence
                    records={comparison.data.analyses}
                    filter={filter}
                    profile={profile}
                    onFilter={(next) => update({ case: next })}
                    onProfile={(next) => update({ focusProfile: next })}
                    onInspect={setInspected}
                  />
                )}
              </>
            ) : null}
          </>
        )}
      </div>
      {active ? <InspectorDialog run={active} onClose={() => setInspected(null)} /> : null}
    </ContentContainer>
  )
}

function Compatibility({ data }: { data: HistoryComparison }) {
  return (
    <details className={styles.compatibility}>
      <summary>
        <span className={styles.statusDot} data-status={data.compatibility.status} />
        {data.compatibility.status === 'incompatible'
          ? 'Settings differ or are unknown'
          : data.compatibility.status === 'exploratory'
            ? 'Exploratory evidence'
            : 'Recorded settings match'}
        <span>Settings and interpretation</span>
      </summary>
      <p>{data.interpretation}</p>
      <ul>
        {data.compatibility.issues.map((issue) => (
          <li key={issue.code + issue.message}>
            {issue.message} <small>({issue.analysisIds.length} records)</small>
          </li>
        ))}
      </ul>
    </details>
  )
}

function InsightsOverview({
  data,
  onInspect,
  onInvestigate,
}: {
  data: HistoryComparison
  onInspect: (id: string) => void
  onInvestigate: (filter: Investigation, profile?: string) => void
}) {
  const evidence = summarizeEvidence(data.analyses)
  const ppoFailures = data.analyses.filter((run) => matchesInvestigation(run, 'ppo_worse')).length
  const dqnFailures = data.analyses.filter((run) => matchesInvestigation(run, 'dqn_worse')).length
  return (
    <>
      <InsightCharts records={data.analyses} onInspect={onInspect} />
      <section aria-labelledby="investigate-heading">
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.eyebrow}>FOLLOW THE EVIDENCE</span>
            <h2 id="investigate-heading">What should we investigate next?</h2>
          </div>
          <span className={styles.muted}>Questions from this selection</span>
        </div>
        <div className={styles.questionGrid}>
          <article>
            <span className={styles.questionNumber}>
              {evidence.baselineLower.length}
              <small>analyses</small>
            </span>
            <h3>When does the baseline do better?</h3>
            <p>
              {ppoFailures} PPO and {dqnFailures} DQN records have higher burden than their paired
              baseline.
            </p>
            <Button variant="ghost" size="sm" onClick={() => onInvestigate('policy_failure')}>
              Investigate failure cases
            </Button>
          </article>
          <article>
            <span className={styles.questionNumber}>
              {evidence.ties.length}
              <small>burden ties</small>
            </span>
            <h3>Same outcome. Same decisions?</h3>
            <p>
              {evidence.differentChoices.length} tied comparisons used different antibiotic
              sequences.
            </p>
            <Button variant="ghost" size="sm" onClick={() => onInvestigate('agreement')}>
              Examine policy agreement
            </Button>
          </article>
          <article>
            <span className={styles.questionNumber}>
              {evidence.gaps.length}
              <small>analyses with gaps</small>
            </span>
            <h3>Where is the evidence incomplete?</h3>
            <p>Trace actions that had no applicable transition data.</p>
            <Button variant="ghost" size="sm" onClick={() => onInvestigate('unsupported')}>
              Inspect transition gaps
            </Button>
          </article>
        </div>
      </section>
      <section className={styles.panel} aria-labelledby="profiles-heading">
        <div className={styles.panelHeading}>
          <div>
            <h2 id="profiles-heading">Starting profiles worth revisiting</h2>
            <p>Repeated profiles can expose variation. Settings and stochastic draws may differ.</p>
          </div>
          <span className={styles.muted}>{evidence.profiles.length} distinct profiles</span>
        </div>
        <div className={styles.profileRows}>
          {evidence.profiles.slice(0, 4).map((group) => (
            <div key={group.profile}>
              <code>{group.profile}</code>
              <span>
                {group.analyses.length} {group.analyses.length === 1 ? 'record' : 'records'}
              </span>
              <span className={styles.profileObservation}>
                {group.varying
                  ? 'Recorded burdens vary'
                  : group.analyses.length > 1
                    ? group.hasRepeatedPolicy
                      ? 'Shared policy values agree'
                      : 'Different policy coverage'
                    : 'One observation'}
              </span>
              <div className="row">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onInvestigate('all', group.profile)}
                >
                  View evidence
                </Button>
                <ButtonLink
                  variant="secondary"
                  size="sm"
                  to={`/app/simulation/new?profile=${group.profile}`}
                >
                  Follow up
                </ButtonLink>
              </div>
            </div>
          ))}
        </div>
      </section>
      <p className={styles.footnote}>
        Descriptive findings from chosen records, not independent performance estimates. Missing
        policies are unavailable, never zero. Research use only.
      </p>
    </>
  )
}

function ExportMenu({
  data,
  collection,
}: {
  data: HistoryComparison
  collection: AnalysisCollection | undefined
}) {
  return (
    <details className={styles.exportMenu}>
      <summary>
        <FiDownload aria-hidden="true" />
        Export selection
      </summary>
      <div>
        <button
          type="button"
          onClick={() =>
            downloadEvidence(
              evidenceReport(data, collection?.name, collection?.question ?? ''),
              'analysis-insights-report.html',
              'text/html;charset=utf-8',
            )
          }
        >
          Research report · HTML / print
        </button>
        <button
          type="button"
          onClick={() =>
            downloadEvidence(
              metricsCsv(data),
              'analysis-insights-metrics.csv',
              'text/csv;charset=utf-8',
            )
          }
        >
          Metric table · CSV
        </button>
        <button
          type="button"
          onClick={() =>
            downloadEvidence(
              JSON.stringify(
                {
                  exportedAtUtc: new Date().toISOString(),
                  collection: collection ?? null,
                  ...data,
                },
                null,
                2,
              ),
              'analysis-insights-evidence.json',
              'application/json',
            )
          }
        >
          Complete evidence · JSON
        </button>
      </div>
    </details>
  )
}

function InspectorDialog({ run, onClose }: { run: SavedAnalysis; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const previous = document.activeElement
    const element = dialog.current
    if (element?.showModal) element.showModal()
    else element?.setAttribute('open', '')
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
      if (previous instanceof HTMLElement) previous.focus()
    }
  }, [])
  return (
    <dialog
      ref={dialog}
      className={styles.inspectorDialog}
      aria-label="Saved analysis evidence"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <AnalysisInspector run={run} onClose={onClose} />
    </dialog>
  )
}
