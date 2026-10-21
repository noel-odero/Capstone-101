import { FiAlertTriangle as TriangleAlert } from 'react-icons/fi'
import { isApiError } from '@/api/api-errors'
import { useHealth } from '@/hooks/useHealth'
import styles from './layout.module.css'

/** Visible only when the API cannot be reached or reports itself not ready; silent when everything is healthy. */
export function ServiceStatusBanner() {
  const health = useHealth()

  if (health.isPending || (health.data?.ready ?? false)) {
    return null
  }

  const unhealthy =
    health.data?.components.filter((component) => component.status !== 'healthy') ?? []
  const message = health.data
    ? `The API reports it is not ready. ${unhealthy
        .map(
          (component) =>
            `${component.name}: ${component.status}${component.detail ? ` (${component.detail})` : ''}`,
        )
        .join('; ')}.`
    : isApiError(health.error)
      ? health.error.message
      : 'The API could not be reached.'

  return (
    <div className={styles['banner']} role="status">
      <TriangleAlert size={16} aria-hidden="true" />
      <strong>Service status</strong>
      <span>{message}</span>
    </div>
  )
}
