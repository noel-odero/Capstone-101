import antibioticsJson from './captured/antibiotics.json'
import comparisonJson from './captured/comparison.json'
import comparisonTerminalJson from './captured/comparison-terminal.json'
import healthJson from './captured/health.json'
import modelJson from './captured/model.json'
import problemNotFoundJson from './captured/problem-not-found.json'
import problemRecommendationNotFoundJson from './captured/problem-recommendation-not-found.json'
import problemValidationJson from './captured/problem-validation.json'
import profileValidationJson from './captured/profile-validation.json'
import profileValidationTerminalJson from './captured/profile-validation-terminal.json'
import recentRunsJson from './captured/recent-runs.json'
import recommendationJson from './captured/recommendation.json'
import simulationBaselineJson from './captured/simulation-baseline.json'
import simulationPpoJson from './captured/simulation-ppo.json'
import {
  antibioticCatalogueSchema,
  comparisonSchema,
  healthSchema,
  modelInfoSchema,
  profileValidationSchema,
  recentRunsSchema,
  recommendationSchema,
  simulationSchema,
  type RecentRuns,
} from '@/domain/types'

/**
 * TEST FIXTURES ONLY. The JSON files in `./captured` are real responses recorded from the running public API
 * (the ASP.NET Core backend over the real Python service and PostgreSQL) for a fixed profile and seeds. They are
 * parsed with the production schemas, so a contract change fails here. Never import this module from production code.
 */
export const rawFixtures = {
  health: healthJson,
  model: modelJson,
  antibiotics: antibioticsJson,
  profileValidation: profileValidationJson,
  profileValidationTerminal: profileValidationTerminalJson,
  comparison: comparisonJson,
  comparisonTerminal: comparisonTerminalJson,
  simulationPpo: simulationPpoJson,
  simulationBaseline: simulationBaselineJson,
  recommendation: recommendationJson,
  recentRuns: recentRunsJson,
  problemValidation: problemValidationJson,
  problemNotFound: problemNotFoundJson,
  problemRecommendationNotFound: problemRecommendationNotFoundJson,
} as const

export const fixtures = {
  health: healthSchema.parse(healthJson),
  model: modelInfoSchema.parse(modelJson),
  antibiotics: antibioticCatalogueSchema.parse(antibioticsJson),
  profileValidation: profileValidationSchema.parse(profileValidationJson),
  profileValidationTerminal: profileValidationSchema.parse(profileValidationTerminalJson),
  comparison: comparisonSchema.parse(comparisonJson),
  comparisonTerminal: comparisonSchema.parse(comparisonTerminalJson),
  simulationPpo: simulationSchema.parse(simulationPpoJson),
  simulationBaseline: simulationSchema.parse(simulationBaselineJson),
  recommendation: recommendationSchema.parse(recommendationJson),
  recentRuns: recentRunsSchema.parse(recentRunsJson),
}

/** An API with no stored runs. Constructed, not captured: it is the documented empty page shape. */
export const emptyRecentRuns: RecentRuns = { items: [], page: 1, pageSize: 10, totalCount: 0 }
