import { problemDetailsSchema, type ProblemDetails } from '@/domain/types'
import { humanise } from '@/domain/terminology'

export type ApiErrorKind =
  | 'validation'
  | 'not_found'
  | 'unauthenticated'
  | 'forbidden'
  | 'unsupported_media_type'
  | 'dependency_unavailable'
  | 'upstream_failure'
  | 'server_error'
  | 'client_error'
  | 'network'
  | 'timeout'
  | 'aborted'
  | 'malformed_response'

export interface ApiErrorInit {
  kind: ApiErrorKind
  message: string
  status?: number
  code?: string
  correlationId?: string
  fieldErrors?: Readonly<Record<string, readonly string[]>>
  cause?: unknown
}

/** A failed API interaction, reduced to what the interface may show. Stack traces and raw bodies never reach it. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | undefined
  readonly code: string | undefined
  readonly correlationId: string | undefined
  readonly fieldErrors: Readonly<Record<string, readonly string[]>>

  constructor(init: ApiErrorInit) {
    super(init.message, { cause: init.cause })
    this.name = 'ApiError'
    this.kind = init.kind
    this.status = init.status
    this.code = init.code
    this.correlationId = init.correlationId
    this.fieldErrors = init.fieldErrors ?? {}
  }

  /** Cancellation is not a failure the user needs to be told about. */
  get isCancellation(): boolean {
    return this.kind === 'aborted'
  }

  /**
   * Whether repeating the same read is reasonable. Used only for GET-style queries; creation requests are never
   * retried automatically, whatever this returns.
   */
  get isTransient(): boolean {
    return this.kind === 'network' || this.kind === 'timeout' || this.kind === 'dependency_unavailable'
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

const MAX_DETAIL_LENGTH = 400

function statusToKind(status: number): ApiErrorKind {
  switch (status) {
    case 404:
      return 'not_found'
    case 401:
      return 'unauthenticated'
    case 403:
      return 'forbidden'
    case 415:
      return 'unsupported_media_type'
    case 422:
      return 'validation'
    case 502:
      return 'upstream_failure'
    case 503:
      return 'dependency_unavailable'
    default:
      return status >= 500 ? 'server_error' : 'client_error'
  }
}

const FALLBACK_MESSAGES: Readonly<Record<ApiErrorKind, string>> = {
  validation: 'The request was not valid. Check the highlighted values and try again.',
  not_found: 'The requested item was not found.',
  unauthenticated: 'Your session has ended. Sign in again to continue.',
  forbidden: 'The request could not be verified. Reload the page and try again.',
  unsupported_media_type: 'The server could not read the request format.',
  dependency_unavailable: 'A service the API depends on is currently unavailable. Try again shortly.',
  upstream_failure: 'The scientific service returned a response the API could not use.',
  server_error: 'The server hit an unexpected problem.',
  client_error: 'The server rejected the request.',
  network: 'The API could not be reached. Check that the backend is running and your connection is working.',
  timeout: 'The request took too long and was stopped.',
  aborted: 'The request was cancelled.',
  malformed_response: 'The server sent a response this application could not understand.',
}

export function fallbackMessage(kind: ApiErrorKind): string {
  return FALLBACK_MESSAGES[kind]
}

/** Backend problem `detail` strings are written for clients; anything long or absent falls back to generic text. */
function safeDetail(problem: ProblemDetails | undefined, kind: ApiErrorKind): string {
  const detail = problem?.detail?.trim()
  return detail && detail.length <= MAX_DETAIL_LENGTH ? detail : FALLBACK_MESSAGES[kind]
}

export function parseProblemDetails(body: unknown): ProblemDetails | undefined {
  const parsed = problemDetailsSchema.safeParse(body)
  return parsed.success ? parsed.data : undefined
}

/** Maps a non-2xx response (and its problem body, when it has one) to an `ApiError`. */
export function errorFromResponse(status: number, body: unknown): ApiError {
  const problem = parseProblemDetails(body)
  const kind = statusToKind(status)
  return new ApiError({
    kind,
    status,
    message: kind === 'validation' ? FALLBACK_MESSAGES.validation : safeDetail(problem, kind),
    ...(problem?.code === undefined ? {} : { code: problem.code }),
    ...(problem?.correlationId === undefined ? {} : { correlationId: problem.correlationId }),
    ...(problem?.errors === undefined ? {} : { fieldErrors: problem.errors }),
  })
}

export function networkError(cause: unknown): ApiError {
  return new ApiError({ kind: 'network', message: FALLBACK_MESSAGES.network, cause })
}

export function timeoutError(): ApiError {
  return new ApiError({ kind: 'timeout', message: FALLBACK_MESSAGES.timeout })
}

export function abortedError(): ApiError {
  return new ApiError({ kind: 'aborted', message: FALLBACK_MESSAGES.aborted })
}

export function malformedResponseError(cause: unknown, status?: number): ApiError {
  return new ApiError({
    kind: 'malformed_response',
    message: FALLBACK_MESSAGES.malformed_response,
    ...(status === undefined ? {} : { status }),
    cause,
  })
}

/** Turns anything thrown into an `ApiError`, so UI code only ever handles one error shape. */
export function normalizeError(error: unknown): ApiError {
  if (isApiError(error)) {
    return error
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return abortedError()
  }
  return new ApiError({ kind: 'server_error', message: FALLBACK_MESSAGES.server_error, cause: error })
}

/** Short heading for an error state. */
export function errorTitle(error: ApiError): string {
  switch (error.kind) {
    case 'validation':
      return 'The request was not accepted'
    case 'not_found':
      return 'Not found'
    case 'unauthenticated':
      return 'Sign in required'
    case 'dependency_unavailable':
      return 'A backend service is unavailable'
    case 'network':
      return 'Cannot reach the API'
    case 'timeout':
      return 'The request timed out'
    case 'malformed_response':
      return 'Unexpected response'
    case 'upstream_failure':
      return 'The scientific service failed'
    default:
      return error.code ? humanise(error.code) : 'Something went wrong'
  }
}
