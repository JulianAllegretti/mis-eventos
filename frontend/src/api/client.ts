import axios, { AxiosError } from 'axios'
import type { ErrorBody } from '@/api/types'

/** Error de la API con el formato estándar `{ code, message, details }` ya normalizado. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: string[]

  constructor(status: number, code: string, message: string, details: string[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

/** Rutas donde un 401 es una respuesta esperada y no significa "sesión caducada". */
const SESSION_PROBE_PATHS = ['/auth/login', '/auth/register', '/auth/me']

let unauthorizedHandler: (() => void) | null = null

/** Permite que la capa de estado reaccione a una sesión caducada sin importar el store aquí. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler
}

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true, // la sesión viaja en una cookie HttpOnly
  headers: { 'Content-Type': 'application/json' },
})

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (axios.isCancel(error)) return new ApiError(0, 'cancelled', 'Petición cancelada')
  if (error instanceof AxiosError) {
    if (!error.response) {
      return new ApiError(
        0,
        'network_error',
        'No se pudo conectar con el servidor. Revisa tu conexión.',
      )
    }
    const { status, data } = error.response
    const body = (data ?? {}) as Partial<ErrorBody>
    return new ApiError(
      status,
      body.code ?? 'unknown_error',
      body.message ?? 'Ocurrió un error inesperado',
      body.details ?? [],
    )
  }
  return new ApiError(0, 'unknown_error', 'Ocurrió un error inesperado')
}

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const apiError = toApiError(error)
    const path = (error instanceof AxiosError ? error.config?.url : undefined) ?? ''
    if (apiError.status === 401 && !SESSION_PROBE_PATHS.some((p) => path.startsWith(p))) {
      unauthorizedHandler?.()
    }
    return Promise.reject(apiError)
  },
)
