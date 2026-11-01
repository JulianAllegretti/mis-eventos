import { toApiError } from '@/api/client'

/** Mensaje legible para mostrar al usuario, incluyendo el detalle de validación si lo hay. */
export function describeError(error: unknown): string {
  const apiError = toApiError(error)
  if (apiError.details.length > 0) return `${apiError.message}: ${apiError.details.join('; ')}`
  return apiError.message
}
