import type { IconType } from 'react-icons'
import { PAGE_TITLES } from '@/domain/terminology'
import {
  FiArchive as Archive,
  FiTrendingUp as ChartLine,
  FiHome as House,
  FiList as ListChecks,
  FiCrosshair as Microscope,
  FiClock as History,
  FiPieChart as Insights,
} from 'react-icons/fi'

export interface NavigationItem {
  to: string
  label: string
  icon: IconType
  /** Match the exact path only (Home would otherwise be active on every workspace page). */
  end?: boolean
  /** Other paths under which this item stays highlighted. */
  alsoActiveFor?: readonly string[]
}

/** Core analysis workflow, sample library and resistance profiles. */
export const workspaceNavigation: readonly NavigationItem[] = [
  { to: '/app', label: PAGE_TITLES.workspace, icon: House, end: true },
  { to: '/app/samples', label: 'Samples', icon: Archive },
  {
    to: '/app/simulation',
    label: PAGE_TITLES.evaluation,
    icon: ChartLine,
    alsoActiveFor: ['/app/simulation'],
  },
  { to: '/app/recommendations', label: PAGE_TITLES.results, icon: ListChecks },
  { to: '/app/history', label: PAGE_TITLES.history, icon: History, end: true },
  { to: '/app/insights', label: PAGE_TITLES.insights, icon: Insights },
  {
    to: '/app/profile',
    label: 'Model Explorer',
    icon: Microscope,
  },
]

export interface PublicLink {
  to: string
  label: string
}

export const publicNavigation: readonly PublicLink[] = [
  { to: '/about', label: 'About' },
  { to: '/methodology', label: 'Methodology' },
  { to: '/limitations', label: 'Limitations' },
  { to: '/documentation', label: 'Documentation' },
]

export const LIMITATIONS_PATH = '/limitations'
export const SIGN_IN_PATH = '/auth/sign-in'
export const WORKSPACE_PATH = '/app'
/** The project's public repository (verified as publicly reachable). */
export const REPOSITORY_URL = 'https://github.com/noel-odero/Capstone-101'
