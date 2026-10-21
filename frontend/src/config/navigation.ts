import {
  FiTrendingUp as ChartLine,
  FiHome as House,
  FiList as ListChecks,
  FiCrosshair as Microscope,
} from 'react-icons/fi'
import type { IconType } from 'react-icons'

export interface NavigationItem {
  to: string
  label: string
  icon: IconType
  /** Match the exact path only (Home would otherwise be active on every workspace page). */
  end?: boolean
  /** Other paths under which this item stays highlighted. */
  alsoActiveFor?: readonly string[]
}

/** The signed-in workspace: four pages. */
export const workspaceNavigation: readonly NavigationItem[] = [
  { to: '/app', label: 'Home', icon: House, end: true },
  { to: '/app/simulation', label: 'Simulation', icon: ChartLine },
  { to: '/app/recommendations', label: 'Recommendations', icon: ListChecks },
  {
    to: '/app/profile',
    label: 'E. coli Profile',
    icon: Microscope,
    alsoActiveFor: ['/app/history'],
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
