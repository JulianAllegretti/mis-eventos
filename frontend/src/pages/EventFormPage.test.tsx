import { fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import EventFormPage from '@/pages/EventFormPage'
import { API } from '@/test/handlers'
import { makeEvent, makeUserWithRole } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage, setAuthenticated } from '@/test/utils'

const create = () => renderPage(<EventFormPage />, { path: '/events/new', url: '/events/new' })
const edit = (id: string) =>
  renderPage(<EventFormPage />, { path: '/events/:id/edit', url: `/events/${id}/edit` })

function setDate(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

async function fillValid(
  user: ReturnType<typeof create>['user'],
  overrides: Record<string, string> = {},
) {
  const values = { Nombre: 'Congreso de Python', Lugar: 'Bogotá', ...overrides }
  await user.type(screen.getByLabelText('Nombre'), values.Nombre!)
  await user.type(screen.getByLabelText('Lugar'), values.Lugar!)
  setDate('Inicio', '2099-05-10T09:00')
  setDate('Fin', '2099-05-10T17:00')
}

describe('EventFormPage: crear', () => {
  beforeEach(() => setAuthenticated(makeUserWithRole('organizer')))

  it('exige los campos obligatorios', async () => {
    const { user } = create()
    await user.clear(screen.getByLabelText('Capacidad'))
    await user.click(screen.getByRole('button', { name: 'Crear evento' }))

    expect(await screen.findByText('El nombre es obligatorio')).toBeInTheDocument()
    expect(screen.getByText('El lugar es obligatorio')).toBeInTheDocument()
    expect(screen.getByText('Indica cuándo empieza')).toBeInTheDocument()
    expect(screen.getByText('Indica cuándo termina')).toBeInTheDocument()
    expect(screen.getByText('Indica la capacidad')).toBeInTheDocument()
  })

  it('el fin debe ser posterior al inicio', async () => {
    const { user } = create()
    await fillValid(user)
    setDate('Fin', '2099-05-10T08:00')
    await user.click(screen.getByRole('button', { name: 'Crear evento' }))

    expect(await screen.findByText('El fin debe ser posterior al inicio')).toBeInTheDocument()
  })

  it('un evento nuevo no puede empezar en el pasado', async () => {
    const { user } = create()
    await fillValid(user)
    setDate('Inicio', '2001-01-01T09:00')
    setDate('Fin', '2001-01-01T10:00')
    await user.click(screen.getByRole('button', { name: 'Crear evento' }))

    expect(await screen.findByText('El inicio debe estar en el futuro')).toBeInTheDocument()
  })

  it.each([
    ['0', 'La capacidad mínima es 1'],
    ['1.5', 'Debe ser un número entero'],
    ['100001', 'La capacidad máxima es 100.000'],
  ])('capacidad %s → «%s»', async (value, message) => {
    const { user } = create()
    await fillValid(user)
    fireEvent.change(screen.getByLabelText('Capacidad'), { target: { value } })
    await user.click(screen.getByRole('button', { name: 'Crear evento' }))

    expect(await screen.findByText(message)).toBeInTheDocument()
  })

  it('envía fechas ISO con zona horaria y la capacidad como número, y abre el evento creado', async () => {
    let body: Record<string, unknown> = {}
    server.use(
      http.post(`${API}/events`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(makeEvent({ id: 'nuevo' }), { status: 201 })
      }),
    )
    const { user } = create()
    await fillValid(user)
    fireEvent.change(screen.getByLabelText('Capacidad'), { target: { value: '120' } })
    await user.type(screen.getByLabelText('Descripción (opcional)'), 'Tres días de charlas')
    await user.click(screen.getByRole('button', { name: 'Crear evento' }))

    expect(await screen.findByText(/evento creado como borrador/i)).toBeInTheDocument()
    expect(body).toMatchObject({
      name: 'Congreso de Python',
      location: 'Bogotá',
      description: 'Tres días de charlas',
      capacity: 120,
    })
    expect(body.start_at).toMatch(/^2099-05-10T.*Z$/)
    expect(body.end_at).toMatch(/Z$/)
    expect(await screen.findByText('otra-ruta')).toBeInTheDocument() // navegó al detalle
  })

  it('una descripción vacía se envía como null', async () => {
    let body: Record<string, unknown> = {}
    server.use(
      http.post(`${API}/events`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(makeEvent(), { status: 201 })
      }),
    )
    const { user } = create()
    await fillValid(user)
    await user.click(screen.getByRole('button', { name: 'Crear evento' }))

    await waitFor(() => expect(body).toHaveProperty('description', null))
  })

  it('muestra los errores de validación que devuelve el servidor', async () => {
    server.use(
      http.post(`${API}/events`, () =>
        HttpResponse.json(
          {
            code: 'validation_failed',
            message: 'Datos de evento inválidos',
            details: ['end_at: debe ser posterior a start_at'],
          },
          { status: 422 },
        ),
      ),
    )
    const { user } = create()
    await fillValid(user)
    await user.click(screen.getByRole('button', { name: 'Crear evento' }))

    expect(await screen.findByText(/Datos de evento inválidos: end_at/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Crear evento' })).toBeEnabled() // puede reintentar
  })
})

describe('EventFormPage: editar', () => {
  beforeEach(() => setAuthenticated(makeUserWithRole('organizer', { id: 'owner' })))

  it('carga el evento en el formulario', async () => {
    const event = makeEvent({
      id: 'e1',
      name: 'Mi evento',
      location: 'Cali',
      capacity: 80,
      organizer_id: 'owner',
    })
    server.use(http.get(`${API}/events/e1`, () => HttpResponse.json(event)))
    edit('e1')

    expect(await screen.findByDisplayValue('Mi evento')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Cali')).toBeInTheDocument()
    expect(screen.getByLabelText('Capacidad')).toHaveValue(80)
    expect(screen.getByRole('heading', { name: 'Editar evento' })).toBeInTheDocument()
  })

  it('guarda los cambios con PATCH', async () => {
    const event = makeEvent({ id: 'e1', name: 'Mi evento', organizer_id: 'owner' })
    let body: Record<string, unknown> = {}
    server.use(
      http.get(`${API}/events/e1`, () => HttpResponse.json(event)),
      http.patch(`${API}/events/e1`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ ...event, name: 'Renombrado' })
      }),
    )
    const { user } = edit('e1')

    const name = await screen.findByDisplayValue('Mi evento')
    await user.clear(name)
    await user.type(name, 'Renombrado')
    await user.click(screen.getByRole('button', { name: 'Guardar cambios' }))

    expect(await screen.findByText('Cambios guardados')).toBeInTheDocument()
    expect(body).toMatchObject({ name: 'Renombrado' })
  })

  it('un evento ya iniciado se puede editar (no exige inicio futuro)', async () => {
    const event = makeEvent({
      id: 'e1',
      start_at: '2020-01-01T09:00:00Z',
      end_at: '2099-01-01T09:00:00Z',
    })
    server.use(
      http.get(`${API}/events/e1`, () => HttpResponse.json(event)),
      http.patch(`${API}/events/e1`, () => HttpResponse.json(event)),
    )
    const { user } = edit('e1')

    await screen.findByDisplayValue(event.name)
    await user.click(screen.getByRole('button', { name: 'Guardar cambios' }))

    expect(await screen.findByText('Cambios guardados')).toBeInTheDocument()
  })

  it('avisa que la capacidad no puede bajar de los inscritos', async () => {
    const event = makeEvent({ id: 'e1', capacity: 50, registered_count: 12, available_slots: 38 })
    server.use(http.get(`${API}/events/e1`, () => HttpResponse.json(event)))
    edit('e1')

    expect(await screen.findByText(/no puede ser menor que los 12 inscritos/i)).toBeInTheDocument()
  })

  it.each(['finished', 'cancelled'] as const)(
    'un evento %s ya no se puede editar',
    async (status) => {
      const event = makeEvent({ id: 'e1', status })
      server.use(http.get(`${API}/events/e1`, () => HttpResponse.json(event)))
      edit('e1')

      expect(await screen.findByText('Este evento ya no se puede editar')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Guardar cambios' })).not.toBeInTheDocument()
    },
  )

  it('si el evento no existe muestra el error', async () => {
    server.use(
      http.get(`${API}/events/zzz`, () =>
        HttpResponse.json({ code: 'not_found', message: 'Evento no encontrado' }, { status: 404 }),
      ),
    )
    edit('zzz')

    expect(await screen.findByText('Evento no encontrado')).toBeInTheDocument()
  })
})
