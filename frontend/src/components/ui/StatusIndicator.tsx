import {
  FiCheckCircle as CircleCheck,
  FiMinusCircle as CircleDashed,
  FiXCircle as CircleX,
  FiDatabase as Database,
  FiInfo as Info,
  FiAlertTriangle as TriangleAlert,
} from 'react-icons/fi'
import type { ReactNode } from 'react'
import { Badge, type BadgeVariant } from './Badge'

export type StatusKind =
  'susceptible' | 'resistant' | 'unsupported' | 'supported' | 'warning' | 'info'

const KIND_STYLE: Record<StatusKind, { variant: BadgeVariant; icon: ReactNode }> = {
  susceptible: { variant: 'susceptible', icon: <CircleCheck size={14} aria-hidden="true" /> },
  resistant: { variant: 'resistant', icon: <CircleX size={14} aria-hidden="true" /> },
  unsupported: { variant: 'unsupported', icon: <CircleDashed size={14} aria-hidden="true" /> },
  supported: { variant: 'info', icon: <Database size={14} aria-hidden="true" /> },
  warning: { variant: 'warning', icon: <TriangleAlert size={14} aria-hidden="true" /> },
  info: { variant: 'info', icon: <Info size={14} aria-hidden="true" /> },
}

export interface StatusIndicatorProps {
  kind: StatusKind
  /** The meaning in words; the icon and colour never carry it alone. */
  label: string
  title?: string
}

export function StatusIndicator({ kind, label, title }: StatusIndicatorProps) {
  const { variant, icon } = KIND_STYLE[kind]
  return (
    <Badge variant={variant} title={title}>
      {icon}
      {label}
    </Badge>
  )
}
