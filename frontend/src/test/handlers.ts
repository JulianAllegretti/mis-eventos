import { http, HttpResponse } from 'msw'

/**
 * Respuestas por defecto: nadie ha iniciado sesión y no hay datos. Cada prueba sobrescribe con
 * `server.use(...)` lo que necesita; cualquier otra petición hace fallar la prueba.
 */
export const API = '*/api/v1'

export const handlers = [
  http.get(`${API}/auth/me`, () =>
    HttpResponse.json(
      { code: 'not_authenticated', message: 'Autenticación requerida', details: [] },
      { status: 401 },
    ),
  ),
  http.get(`${API}/events`, () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 9 }),
  ),
]
