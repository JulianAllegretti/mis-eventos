import { http, HttpResponse } from 'msw'
import { api, ApiError, setUnauthorizedHandler, toApiError } from '@/api/client'
import { API } from '@/test/handlers'
import { server } from '@/test/server'

describe('cliente HTTP', () => {
  afterEach(() => setUnauthorizedHandler(null))

  it('normaliza el formato estándar de error de la API', async () => {
    server.use(
      http.get(`${API}/boom`, () =>
        HttpResponse.json(
          { code: 'event_full', message: 'El evento no tiene cupos disponibles', details: ['x'] },
          { status: 409 },
        ),
      ),
    )

    const error = await api.get('/boom').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 409,
      code: 'event_full',
      message: 'El evento no tiene cupos disponibles',
      details: ['x'],
    })
  })

  it('tolera respuestas de error sin el formato esperado', async () => {
    server.use(http.get(`${API}/boom`, () => new HttpResponse('Bad Gateway', { status: 502 })))
    const error = await api.get('/boom').catch((e) => e)
    expect(error).toMatchObject({ status: 502, code: 'unknown_error' })
    expect(error.message).toBeTruthy()
  })

  it('traduce un fallo de red a un mensaje comprensible', async () => {
    server.use(http.get(`${API}/boom`, () => HttpResponse.error()))
    const error = await api.get('/boom').catch((e) => e)
    expect(error).toMatchObject({ status: 0, code: 'network_error' })
    expect(error.message).toMatch(/conectar/i)
  })

  it('toApiError conserva un ApiError y envuelve cualquier otra cosa', () => {
    const original = new ApiError(404, 'not_found', 'No existe')
    expect(toApiError(original)).toBe(original)
    expect(toApiError(new Error('x'))).toMatchObject({ code: 'unknown_error' })
  })

  it('avisa de una sesión caducada con un 401 en rutas normales', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    server.use(
      http.get(`${API}/events/1`, () =>
        HttpResponse.json({ code: 'not_authenticated', message: 'x' }, { status: 401 }),
      ),
    )

    await api.get('/events/1').catch(() => undefined)

    expect(handler).toHaveBeenCalledOnce()
  })

  it.each(['/auth/me', '/auth/login', '/auth/register'])(
    'un 401 en %s es esperado y no se trata como sesión caducada',
    async (path) => {
      const handler = vi.fn()
      setUnauthorizedHandler(handler)
      server.use(
        http.all(`${API}${path}`, () =>
          HttpResponse.json({ code: 'not_authenticated', message: 'x' }, { status: 401 }),
        ),
      )

      await api.request({ url: path, method: 'POST' }).catch(() => undefined)

      expect(handler).not.toHaveBeenCalled()
    },
  )

  it('envía las cookies de sesión (withCredentials)', () => {
    expect(api.defaults.withCredentials).toBe(true)
  })
})
