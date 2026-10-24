import { createBrowserRouter, createMemoryRouter, type RouteObject } from 'react-router'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { WorkspaceLayout } from '@/components/layout/WorkspaceLayout'
import { LoadingState } from '@/components/ui/LoadingState'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { AuthRoot } from './AuthRoot'
import { NotFoundPage } from './NotFoundPage'
import { RouteError } from './RouteError'

// Pages load per route, so charts and the 3D scenes only download with the pages that use them.
const lazyPage = <Module extends Record<string, unknown>>(
  load: () => Promise<Module>,
  name: keyof Module & string,
) => ({
  lazy: async () => ({ Component: (await load())[name] as React.ComponentType }),
})

export const routes: RouteObject[] = [
  {
    element: <AuthRoot />,
    errorElement: <RouteError />,
    hydrateFallbackElement: <LoadingState label="Loading the application" lines={3} block />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { path: '/', ...lazyPage(() => import('@/features/landing/LandingPage'), 'LandingPage') },
          {
            path: '/about',
            ...lazyPage(() => import('@/features/public-pages/AboutPage'), 'AboutPage'),
          },
          {
            path: '/methodology',
            ...lazyPage(() => import('@/features/public-pages/MethodologyPage'), 'MethodologyPage'),
          },
          {
            path: '/limitations',
            ...lazyPage(() => import('@/features/public-pages/LimitationsPage'), 'LimitationsPage'),
          },
          {
            path: '/documentation',
            ...lazyPage(
              () => import('@/features/public-pages/DocumentationPage'),
              'DocumentationPage',
            ),
          },
          {
            path: '/privacy',
            ...lazyPage(() => import('@/features/public-pages/PrivacyPage'), 'PrivacyPage'),
          },
          {
            path: '/auth/sign-in',
            ...lazyPage(() => import('@/features/auth/SignInPage'), 'SignInPage'),
          },
          {
            path: '/auth/register',
            ...lazyPage(() => import('@/features/auth/RegisterPage'), 'RegisterPage'),
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
      {
        path: '/app',
        element: <ProtectedRoute />,
        children: [
          {
            element: <WorkspaceLayout />,
            children: [
              {
                index: true,
                ...lazyPage(() => import('@/features/dashboard/DashboardPage'), 'DashboardPage'),
              },
              {
                path: 'simulation',
                ...lazyPage(
                  () => import('@/features/simulation/SimulationIndex'),
                  'SimulationIndex',
                ),
              },
              {
                path: 'simulation/new',
                ...lazyPage(
                  () => import('@/features/simulation/NewSimulationPage'),
                  'NewSimulationPage',
                ),
              },
              {
                path: 'simulation/:comparisonId',
                ...lazyPage(() => import('@/features/simulation/SimulationPage'), 'SimulationPage'),
              },
              {
                path: 'recommendations',
                ...lazyPage(
                  () => import('@/features/recommendation/RecommendationsIndex'),
                  'RecommendationsIndex',
                ),
              },
              {
                path: 'recommendations/comparison/:comparisonId',
                ...lazyPage(
                  () => import('@/features/recommendation/RecommendationPage'),
                  'RecommendationPage',
                ),
              },
              {
                path: 'recommendations/simulation/:simulationId',
                ...lazyPage(
                  () => import('@/features/recommendation/RecommendationPage'),
                  'RecommendationPage',
                ),
              },
              {
                path: 'profile',
                ...lazyPage(() => import('@/features/profile/ProfilePage'), 'ProfilePage'),
              },
              {
                path: 'history/analyze',
                ...lazyPage(
                  () => import('@/features/history/AnalysisInsightsPage'),
                  'LegacyInsightsRedirect',
                ),
              },
              {
                path: 'insights',
                ...lazyPage(
                  () => import('@/features/history/AnalysisInsightsPage'),
                  'AnalysisInsightsPage',
                ),
              },
              {
                path: 'history',
                ...lazyPage(() => import('@/features/profile/HistoryPage'), 'HistoryPage'),
              },
              {
                path: 'samples',
                ...lazyPage(() => import('@/features/samples/SamplesPage'), 'SamplesPage'),
              },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(routes)
}

/** Same routes without a browser, for component tests. */
export function createTestRouter(initialEntries: string[]) {
  return createMemoryRouter(routes, { initialEntries })
}
