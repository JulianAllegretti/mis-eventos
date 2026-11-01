import { delay, http, HttpResponse } from 'msw'
import { useEventsStore } from '@/stores/eventsStore'
import { API } from '@/test/handlers'
import { makeEvent, page } from '@/test/factories'
import { server } from '@/test/server'

const state = () => useEventsStore.getState()

describe('eventsStore', () => {
  it('fetchList guarda los eventos y la paginación', async () => {
    const events = [makeEvent(), makeEvent()]
    server.use(http.get(`${API}/events`, () => HttpResponse.json(page(events, 25, 2, 9))))

    await state().fetchList({ page: 2 })

    expect(state()).toMatchObject({ total: 25, page: 2, pageSize: 9, loading: false, error: null })
    expect(state().items).toEqual(events)
  })

  it('envía los filtros como parámetros de consulta', async () => {
    let url = ''
    server.use(
      http.get(`${API}/events`, ({ request }) => {
        url = request.url
        return HttpResponse.json(page([]))
      }),
    )

    await state().fetchList({ q: 'python', status: 'published', page: 3, page_size: 9 })

    const params = new URL(url).searchParams
    expect(Object.fromEntries(params)).toEqual({
      q: 'python',
      status: 'published',
      page: '3',
      page_size: '9',
    })
  })

  it('guarda el error si la API falla', async () => {
    server.use(
      http.get(`${API}/events`, () =>
        HttpResponse.json({ code: 'internal_error', message: 'Error interno' }, { status: 500 }),
      ),
    )

    await state().fetchList({})

    expect(state().error).toMatchObject({ status: 500, message: 'Error interno' })
    expect(state().loading).toBe(false)
  })

  it('descarta la respuesta de una búsqueda vieja si llegó una más reciente', async () => {
    const slow = makeEvent({ name: 'Resultado viejo' })
    const fast = makeEvent({ name: 'Resultado nuevo' })
    server.use(
      http.get(`${API}/events`, async ({ request }) => {
        const q = new URL(request.url).searchParams.get('q')
        if (q === 'a') {
          await delay(150)
          return HttpResponse.json(page([slow]))
        }
        return HttpResponse.json(page([fast]))
      }),
    )

    const first = state().fetchList({ q: 'a' })
    const second = state().fetchList({ q: 'ab' })
    await Promise.all([first, second])
    await delay(200)

    expect(state().items.map((e) => e.name)).toEqual(['Resultado nuevo'])
  })

  it('fetchEvent carga el evento actual y registra el 404', async () => {
    const event = makeEvent()
    server.use(
      http.get(`${API}/events/${event.id}`, () => HttpResponse.json(event)),
      http.get(`${API}/events/missing`, () =>
        HttpResponse.json({ code: 'not_found', message: 'Evento no encontrado' }, { status: 404 }),
      ),
    )

    expect(await state().fetchEvent(event.id)).toEqual(event)
    expect(state().current).toEqual(event)

    expect(await state().fetchEvent('missing')).toBeNull()
    expect(state()).toMatchObject({ current: null, currentError: { status: 404 } })
  })

  it('clearCurrent limpia el evento y cancela cargas en curso', () => {
    useEventsStore.setState({ current: makeEvent(), currentLoading: true })
    state().clearCurrent()
    expect(state()).toMatchObject({ current: null, currentLoading: false, currentError: null })
  })
})
