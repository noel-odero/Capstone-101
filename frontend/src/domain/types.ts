import { z } from 'zod'

/**
 * Wire types for the public AMR API (`/api/v1`). Each zod schema mirrors a DTO in
 * `backend/src/Amr.Application/DTOs` and is the only place a response shape is declared:
 * the exported TypeScript types are inferred from the schemas, so they cannot drift apart.
 * Responses are validated at the HTTP boundary; unknown extra members are ignored.
 */

const nullableString = z.string().nullable()

export const resistanceStateSchema = z.union([z.literal(0), z.literal(1)])
export const resistanceProfileSchema = z.array(resistanceStateSchema).length(7)

export const strategyIdSchema = z.enum(['ppo', 'random_susceptible_baseline'])
export const runStatusSchema = z.enum(['completed', 'failed'])
export const experimentKindSchema = z.enum(['simulation', 'comparison'])
export const metricKindSchema = z.enum(['cumulative', 'count', 'difference', 'rate'])
export const healthStateSchema = z.enum(['healthy', 'degraded', 'unhealthy'])

export const antibioticSchema = z.object({
  actionId: z.number().int(),
  name: z.string(),
  drugClass: nullableString,
})

export const antibioticCatalogueSchema = z.object({
  antibiotics: z.array(antibioticSchema),
  resistanceEncoding: z.record(z.string(), z.number()),
})

export const feasibleActionSchema = z.object({
  actionId: z.number().int(),
  antibiotic: z.string(),
  hasCandidateTransition: z.boolean(),
})

const componentHealthSchema = z.object({
  name: z.string(),
  status: healthStateSchema,
  detail: nullableString,
})

export const healthSchema = z.object({
  status: healthStateSchema,
  ready: z.boolean(),
  components: z.array(componentHealthSchema),
})

export const modelInfoSchema = z.object({
  manifestVersion: z.number().int(),
  modelId: z.string(),
  algorithm: z.string(),
  checkpointSha256: z.string(),
  interactionDataSha256: z.string(),
  scenarioId: z.string(),
  horizon: z.number().int(),
  antibioticOrder: z.array(z.string()),
  observation: z.object({
    shape: z.array(z.number().int()),
    dtype: z.string(),
    layout: z.record(z.string(), z.array(z.number().int())),
    resistanceEncoding: z.record(z.string(), z.number()),
  }),
  actionSpace: z.object({ type: z.string(), count: z.number().int() }),
  actionMaskRule: z.string(),
  deterministicInference: z.boolean(),
  transitionStatusDefinitions: z.record(z.string(), z.string()),
  serviceVersion: z.string(),
  disclaimer: z.string(),
})

export const modelProvenanceSchema = z.object({
  modelId: z.string(),
  algorithm: z.string(),
  checkpointSha256: z.string(),
  interactionDataSha256: z.string(),
  scenarioId: z.string(),
  horizon: z.number().int(),
  rewardSpecification: z.record(z.string(), z.unknown()),
  actionMaskRule: z.string(),
  antibioticOrder: z.array(z.string()),
  serviceVersion: z.string(),
})

export const seedConfigurationSchema = z.object({
  environmentSeed: z.number(),
  environmentSeedSource: z.string(),
  policySeed: z.number().nullable(),
  policySeedSource: z.string(),
  notes: z.array(z.string()),
})

export const metricDefinitionSchema = z.object({
  definition: z.string(),
  kind: metricKindSchema,
  unit: z.string(),
  aggregation: z.string(),
})

export const metricDefinitionsSchema = z.record(z.string(), metricDefinitionSchema)

export const runErrorSchema = z.object({ code: z.string(), message: z.string() })

export const stateSnapshotSchema = z.object({
  stateIndex: z.number().int(),
  treatmentStep: z.number().int(),
  resistanceProfile: resistanceProfileSchema,
  resistantAntibiotics: z.array(z.string()),
  resistantCount: z.number().int(),
  susceptibleCount: z.number().int(),
  lastActionId: z.number().int().nullable(),
  lastActionAntibiotic: nullableString,
  isTerminal: z.boolean(),
})

export const candidateTransitionSchema = z.object({
  targetDrug: z.string(),
  outcome: z.string(),
  sourceIds: z.array(z.string()),
  scenarioProbability: z.number(),
})

export const stepTraceSchema = z.object({
  stepIndex: z.number().int(),
  treatmentStepBefore: z.number().int(),
  treatmentStepAfter: z.number().int(),
  resistanceProfileBefore: resistanceProfileSchema,
  actionId: z.number().int(),
  antibiotic: z.string(),
  feasibleActions: z.array(feasibleActionSchema),
  selectedDrugSusceptible: z.boolean(),
  transitionStatus: z.string(),
  hasCandidateTransition: z.boolean(),
  candidateTransitions: z.array(candidateTransitionSchema),
  selectedOutcome: nullableString,
  selectedTargetDrug: nullableString,
  sourceIds: z.array(z.string()),
  selectedCandidateProbability: z.number().nullable(),
  noTransitionProbability: z.number().nullable(),
  transitionSeed: z.number().nullable(),
  reward: z.number(),
  resistanceProfileAfter: resistanceProfileSchema,
  newlyResistantAntibiotics: z.array(z.string()),
  newlySusceptibleAntibiotics: z.array(z.string()),
  resistantCountAfter: z.number().int(),
  susceptibleCountAfter: z.number().int(),
  isTerminalAfter: z.boolean(),
  terminationReason: nullableString,
})

export const strategyMetricsSchema = z.object({
  cumulativeResistanceBurden: z.number(),
  cumulativeReward: z.number(),
  treatmentSteps: z.number().int(),
  initialResistantCount: z.number().int(),
  finalResistantCount: z.number().int(),
  finalSusceptibleCount: z.number().int(),
  changeInSusceptibleCount: z.number().int(),
  resistanceEmergenceEvents: z.number().int(),
  resistanceEmergenceRate: z.number().nullable(),
  susceptibleActionRate: z.number().nullable(),
  unsupportedStepCount: z.number().int(),
  cumulativeAntibioticExposure: z.number().int(),
})

export const strategyResultSchema = z.object({
  strategy: strategyIdSchema,
  displayLabel: z.string(),
  initialProfile: resistanceProfileSchema,
  finalProfile: resistanceProfileSchema,
  environmentSeed: z.number(),
  policySeed: z.number().nullable(),
  terminationReason: z.string(),
  states: z.array(stateSnapshotSchema),
  steps: z.array(stepTraceSchema),
  metrics: strategyMetricsSchema,
})

const runCommonShape = {
  id: z.string().uuid(),
  status: runStatusSchema,
  isPersisted: z.boolean(),
  createdAtUtc: z.string(),
  provenance: modelProvenanceSchema,
  seedConfiguration: seedConfigurationSchema,
  error: runErrorSchema.nullable(),
  metricDefinitions: metricDefinitionsSchema,
  disclaimer: z.string(),
}

export const simulationSchema = z.object({
  ...runCommonShape,
  result: strategyResultSchema.nullable(),
})

export const comparisonContractSchema = z.object({
  verified: z.boolean(),
  checksPassed: z.array(z.string()),
  shared: z.object({
    initialProfile: resistanceProfileSchema,
    environmentSeed: z.number(),
    scenarioId: z.string(),
    horizon: z.number().int(),
    interactionDataSha256: z.string(),
    rewardSpecification: z.record(z.string(), z.unknown()),
    actionMaskConfiguration: z.object({ enabled: z.boolean(), rule: z.string() }),
  }),
  transitionSeedSchedule: z.object({
    sharedByStepIndex: z.boolean(),
    stepsCompared: z.number().int(),
    meaning: z.string(),
  }),
  transitionOutcomesGuaranteedIdentical: z.boolean(),
  observed: z.object({
    stepsCompared: z.number().int(),
    stepsWithSameAction: z.number().int(),
    firstDivergentStep: z.number().int().nullable(),
    trajectoriesIdentical: z.boolean(),
  }),
})

export const comparisonSchema = z.object({
  sampleId: z.string().uuid().nullable().optional(),
  ...runCommonShape,
  pairingSemantics: z.string(),
  contract: comparisonContractSchema.nullable(),
  ppo: strategyResultSchema.nullable(),
  baseline: strategyResultSchema.nullable(),
  singleRunCaveat: z.string(),
})

export const strategySummarySchema = z.object({
  strategy: strategyIdSchema,
  displayLabel: z.string(),
  cumulativeResistanceBurden: z.number(),
  finalResistantCount: z.number().int(),
  terminationReason: z.string(),
})

export const runSummarySchema = z.object({
  id: z.string().uuid(),
  kind: experimentKindSchema,
  status: runStatusSchema,
  createdAtUtc: z.string(),
  initialProfile: resistanceProfileSchema,
  modelId: z.string(),
  strategies: z.array(strategySummarySchema),
})

export const recentRunsSchema = z.object({
  items: z.array(runSummarySchema),
  page: z.number().int(),
  pageSize: z.number().int(),
  totalCount: z.number().int(),
})

export const problemDetailsSchema = z.object({
  title: z.string().optional(),
  status: z.number().optional(),
  detail: z.string().optional(),
  code: z.string().optional(),
  correlationId: z.string().optional(),
  errors: z.record(z.string(), z.array(z.string())).optional(),
})

export type ResistanceState = z.infer<typeof resistanceStateSchema>
export type ResistanceProfile = z.infer<typeof resistanceProfileSchema>
export type StrategyId = z.infer<typeof strategyIdSchema>
export type RunStatus = z.infer<typeof runStatusSchema>
export type Antibiotic = z.infer<typeof antibioticSchema>
export type AntibioticCatalogue = z.infer<typeof antibioticCatalogueSchema>
export type Health = z.infer<typeof healthSchema>
export type ModelInfo = z.infer<typeof modelInfoSchema>
export type ModelProvenance = z.infer<typeof modelProvenanceSchema>
export type MetricDefinitions = z.infer<typeof metricDefinitionsSchema>
export type StateSnapshot = z.infer<typeof stateSnapshotSchema>
export type StepTrace = z.infer<typeof stepTraceSchema>
export type StrategyMetrics = z.infer<typeof strategyMetricsSchema>
export type StrategyResult = z.infer<typeof strategyResultSchema>
export type Simulation = z.infer<typeof simulationSchema>
export type Comparison = z.infer<typeof comparisonSchema>
export type RunSummary = z.infer<typeof runSummarySchema>
export type RecentRuns = z.infer<typeof recentRunsSchema>
export type ProblemDetails = z.infer<typeof problemDetailsSchema>

/** `POST /comparisons` body. Both strategies always run; seeds are generated by the service when omitted. */
export interface CreateComparisonRequest {
  sampleId?: string
  resistanceProfile: ResistanceProfile
  environmentSeed?: number
  policySeed?: number
}
