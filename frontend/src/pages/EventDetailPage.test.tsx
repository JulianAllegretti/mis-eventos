import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { AgendaSession, AppEvent, MyRegistration } from '@/api/types'
import EventDetailPage from '@/pages/EventDetailPage'
import { API } from '@/test/handlers'
import {
  makeAttendee,
  makeEvent,
  makeRegistration,
  makeSession,
  makeSpeaker,
  makeUserWithRole,
  page,
} from '@/test/factories'
import { server } from '@/test/server'
import { renderPage, setAnonymous, setAuthenticated } from '@/test/utils'

const error = (status: number, code: string, message: string) =>
  HttpResponse.json({ code, message, details: [] }, { status })

/** Un "backend" mínimo con estado para recorrer flujos completos. */
function backend(initial: { event: AppEvent; sessions?: AgendaSession[]; registered?: boolean }) {
  const state = {
    event: initial.event,
    sessions: initial.sessions ?? [],
    registered: initial.registered ?? false,
    enrolled: new Set<string>(),
    calls: [] as string[],
  }
  const mine = (): MyRegistration[] =>
    state.registered
      ? [
          makeRegistration(
            state.event,
            state.sessions.filter((s) => state.enrolled.has(s.id)),
          ),
        ]
      : []

  server.use(
    http.get(`${API}/events/${state.event.id}`, () => HttpResponse.json(state.event)),
    http.get(`${API}/events/${state.event.id}/sessions`, () => HttpResponse.json(state.sessions)),
    http.get(`${API}/users/me/registrations`, () => HttpResponse.json(mine())),
    http.post(`${API}/events/${state.event.id}/registrations`, () => {
      state.calls.push('register')
      state.registered = true
      state.event = {
        ...state.event,
        registered_count: state.event.registered_count + 1,
        available_slots: state.event.available_slots - 1,
      }
      return HttpResponse.json(
        { id: 'r1', event_id: state.event.id, created_at: '2030-01-01T00:00:00Z' },
        { status: 201 },
      )
    }),
    http.delete(`${API}/events/${state.event.id}/registrations/me`, () => {
      state.calls.push('cancel')
      state.registered = false
      state.enrolled.clear()
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(`${API}/sessions/:id/registrations`, ({ params }) => {
      state.calls.push(`enroll:${params.id}`)
      state.enrolled.add(String(params.id))
      return HttpResponse.json(
        { id: 's', session_id: params.id, created_at: '2030-01-01T00:00:00Z' },
        { status: 201 },
      )
    }),
    http.delete(`${API}/sessions/:id/registrations/me`, ({ params }) => {
      state.calls.push(`leave:${params.id}`)
      state.enrolled.delete(String(params.id))
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return state
}

const open = (event: AppEvent) =>
  renderPage(<EventDetailPage />, { path: '/events/:id', url: `/events/${event.id}` })

describe('EventDetailPage: información', () => {
  it('muestra los datos del evento, su descripción y su agenda', async () => {
    const event = makeEvent({
      name: 'Congreso de Python',
      description: 'Tres días de charlas',
      location: 'Medellín',
    })
    backend({ event, sessions: [makeSession({ title: 'Intro a FastAPI' })] })
    setAnonymous()
    open(event)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Congreso de Python' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Tres días de charlas')).toBeInTheDocument()
    expect(screen.getByText('Medellín')).toBeInTheDocument()
    expect(await screen.findByText('Intro a FastAPI')).toBeInTheDocument()
    expect(screen.getByText('Ana Pérez')).toBeInTheDocument() // ponente
  })

  it('indica cuando no hay sesiones programadas', async () => {
    const event = makeEvent()
    backend({ event })
    setAnonymous()
    open(event)

    expect(await screen.findByText(/aún no tiene sesiones/i)).toBeInTheDocument()
  })

  it('un evento inexistente muestra "no encontrado"', async () => {
    server.use(
      http.get(`${API}/events/zzz`, () => error(404, 'not_found', 'Evento no encontrado')),
      http.get(`${API}/events/zzz/sessions`, () => error(404, 'not_found', 'Evento no encontrado')),
    )
    setAnonymous()
    renderPage(<EventDetailPage />, { path: '/events/:id', url: '/events/zzz' })

    expect(await screen.findByText('Evento no encontrado')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver eventos' })).toBeInTheDocument()
  })

  it.each([
    ['draft', /todavía no admite inscripciones/i],
    ['finished', /ya finalizó/i],
    ['cancelled', /fue cancelado/i],
  ] as const)('un evento %s no admite inscripciones y lo explica', async (status, message) => {
    const event = makeEvent({ status })
    backend({ event })
    setAuthenticated(makeUserWithRole('attendee'))
    open(event)

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Inscribirme' })).not.toBeInTheDocument()
  })
})

describe('EventDetailPage: inscripción', () => {
  it('un anónimo ve la invitación a ingresar', async () => {
    const event = makeEvent()
    backend({ event })
    setAnonymous()
    open(event)

    const link = await screen.findByRole('link', { name: 'Ingresa para inscribirte' })
    expect(link).toHaveAttribute('href', '/login')
  })

  it('un asistente se inscribe, ve su estado y los cupos se actualizan', async () => {
    const event = makeEvent({ capacity: 10, registered_count: 3, available_slots: 7 })
    const server_ = backend({ event })
    setAuthenticated(makeUserWithRole('attendee'))
    const { user } = open(event)

    await user.click(await screen.findByRole('button', { name: 'Inscribirme' }))

    expect(await screen.findByText('¡Listo! Quedaste inscrito al evento')).toBeInTheDocument()
    expect(await screen.findByText('Estás inscrito')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancelar inscripción' })).toBeInTheDocument()
    expect(screen.getByText('6 de 10 cupos disponibles')).toBeInTheDocument()
    expect(server_.calls).toEqual(['register'])
  })

  it('con el evento lleno el botón queda deshabilitado', async () => {
    const event = makeEvent({ capacity: 5, registered_count: 5, available_slots: 0 })
    backend({ event })
    setAuthenticated(makeUserWithRole('attendee'))
    open(event)

    expect(await screen.findByRole('button', { name: 'Sin cupos disponibles' })).toBeDisabled()
  })

  it('si el servidor responde "evento lleno" lo comunica y refresca los cupos', async () => {
    const event = makeEvent({ capacity: 5, registered_count: 4, available_slots: 1 })
    backend({ event })
    server.use(
      http.post(`${API}/events/${event.id}/registrations`, () =>
        error(409, 'event_full', 'El evento no tiene cupos disponibles'),
      ),
    )
    setAuthenticated(makeUserWithRole('attendee'))
    const { user } = open(event)

    const button = await screen.findByRole('button', { name: 'Inscribirme' }) // la página ya cargó
    // Mientras tanto otra persona toma el último cupo.
    server.use(
      http.get(`${API}/events/${event.id}`, () =>
        HttpResponse.json({ ...event, registered_count: 5, available_slots: 0 }),
      ),
    )
    await user.click(button)

    expect(await screen.findByText('El evento no tiene cupos disponibles')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Sin cupos disponibles' })).toBeDisabled()
  })

  it('cancelar la inscripción pide confirmación y libera el cupo', async () => {
    const event = makeEvent({ capacity: 10, registered_count: 1, available_slots: 9 })
    const server_ = backend({ event, registered: true })
    setAuthenticated(makeUserWithRole('attendee'))
    const { user } = open(event)

    await user.click(await screen.findByRole('button', { name: 'Cancelar inscripción' }))
    const dialog = await screen.findByRole('dialog')
    expect(server_.calls).toEqual([]) // todavía no se canceló
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar inscripción' }))

    expect(await screen.findByRole('button', { name: 'Inscribirme' })).toBeInTheDocument()
    expect(server_.calls).toEqual(['cancel'])
  })
})

describe('EventDetailPage: sesiones del asistente', () => {
  const sessions = () => [
    makeSession({ id: 's1', title: 'Introducción', capacity: 20 }),
    makeSession({ id: 's2', title: 'Taller lleno', capacity: 2, registered_count: 2 }),
  ]

  it('antes de inscribirse al evento no puede elegir sesiones', async () => {
    const event = makeEvent()
    backend({ event, sessions: sessions() })
    setAuthenticated(makeUserWithRole('attendee'))
    open(event)

    expect(await screen.findByText(/inscríbete al evento para poder elegir/i)).toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: 'Inscribirme' })).toHaveLength(1) // solo el del evento
  })

  it('inscrito al evento puede unirse y salir de una sesión', async () => {
    const event = makeEvent()
    const server_ = backend({ event, sessions: sessions(), registered: true })
    setAuthenticated(makeUserWithRole('attendee'))
    const { user } = open(event)

    const intro = (await screen.findByText('Introducción')).closest('li')!
    await user.click(within(intro).getByRole('button', { name: 'Inscribirme' }))

    expect(await within(intro).findByText('Inscrito')).toBeInTheDocument()
    await user.click(within(intro).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(within(intro).queryByText('Inscrito')).not.toBeInTheDocument())
    expect(server_.calls).toEqual(['enroll:s1', 'leave:s1'])
  })

  it('una sesión llena muestra "Sin cupos" y no ofrece inscribirse', async () => {
    const event = makeEvent()
    backend({ event, sessions: sessions(), registered: true })
    setAuthenticated(makeUserWithRole('attendee'))
    open(event)

    const full = (await screen.findByText('Taller lleno')).closest('li')!
    expect(within(full).getByText('Sin cupos')).toBeInTheDocument()
    expect(within(full).queryByRole('button', { name: 'Inscribirme' })).not.toBeInTheDocument()
  })

  it('un choque de horario del servidor se muestra al usuario', async () => {
    const event = makeEvent()
    backend({ event, sessions: sessions(), registered: true })
    server.use(
      http.post(`${API}/sessions/s1/registrations`, () =>
        error(409, 'schedule_conflict', 'Ya estás inscrito en otra sesión en ese horario'),
      ),
    )
    setAuthenticated(makeUserWithRole('attendee'))
    const { user } = open(event)

    const intro = (await screen.findByText('Introducción')).closest('li')!
    await user.click(within(intro).getByRole('button', { name: 'Inscribirme' }))

    expect(
      await screen.findByText('Ya estás inscrito en otra sesión en ese horario'),
    ).toBeInTheDocument()
  })
})

describe('EventDetailPage: gestión', () => {
  it('el organizador dueño ve las acciones; otro organizador y los asistentes no', async () => {
    const event = makeEvent({ organizer_id: 'owner-1', status: 'draft' })
    backend({ event })

    setAuthenticated(makeUserWithRole('organizer', { id: 'owner-1' }))
    const owner = open(event)
    expect(await screen.findByRole('link', { name: /editar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /publicar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /agregar sesión/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ver asistentes/i })).toBeInTheDocument()
    owner.unmount()

    setAuthenticated(makeUserWithRole('organizer', { id: 'otro' }))
    const other = open(event)
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByRole('button', { name: /publicar/i })).not.toBeInTheDocument()
    other.unmount()

    setAuthenticated(makeUserWithRole('admin'))
    open(event)
    expect(await screen.findByRole('button', { name: /publicar/i })).toBeInTheDocument() // admin gestiona todo
  })

  it('publicar pide confirmación y actualiza el estado', async () => {
    const event = makeEvent({ organizer_id: 'owner-1', status: 'draft' })
    backend({ event })
    server.use(
      http.post(`${API}/events/${event.id}/publish`, () =>
        HttpResponse.json({ ...event, status: 'published' }),
      ),
    )
    setAuthenticated(makeUserWithRole('organizer', { id: 'owner-1' }))
    const { user } = open(event)

    await user.click(await screen.findByRole('button', { name: /publicar/i }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Publicar' }))

    expect(await screen.findByText('Evento publicado')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /publicar/i })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: /finalizar/i })).toBeInTheDocument()
  })

  it('un error del servidor al borrar se muestra y no se pierde el evento', async () => {
    const event = makeEvent({ organizer_id: 'owner-1', registered_count: 2, available_slots: 48 })
    backend({ event })
    server.use(
      http.delete(`${API}/events/${event.id}`, () =>
        error(409, 'conflict', 'El evento tiene inscripciones: cancélalo en lugar de borrarlo'),
      ),
    )
    setAuthenticated(makeUserWithRole('organizer', { id: 'owner-1' }))
    const { user } = open(event)

    await user.click(await screen.findByRole('button', { name: /borrar/i }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Borrar' }))

    expect(await screen.findByText(/cancélalo en lugar de borrarlo/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: event.name })).toBeInTheDocument()
  })

  it('el organizador consulta la lista de asistentes', async () => {
    const event = makeEvent({ organizer_id: 'owner-1', registered_count: 2, available_slots: 48 })
    backend({ event })
    server.use(
      http.get(`${API}/events/${event.id}/registrations`, () =>
        HttpResponse.json(
          page(
            [makeAttendee({ full_name: 'Carla Ruiz' }), makeAttendee({ full_name: 'Diego Mora' })],
            2,
            1,
            10,
          ),
        ),
      ),
    )
    setAuthenticated(makeUserWithRole('organizer', { id: 'owner-1' }))
    const { user } = open(event)

    await user.click(await screen.findByRole('button', { name: /ver asistentes/i }))

    expect(await screen.findByText('Carla Ruiz')).toBeInTheDocument()
    expect(screen.getByText('Diego Mora')).toBeInTheDocument()
  })

  it('el organizador crea una sesión con ponente desde la agenda', async () => {
    const event = makeEvent({
      organizer_id: 'owner-1',
      start_at: '2030-05-10T14:00:00Z',
      end_at: '2030-05-10T22:00:00Z',
      capacity: 100,
    })
    const state = backend({ event })
    const speaker = makeSpeaker({ id: 'sp-1', name: 'Marta Díaz' })
    let posted: Record<string, unknown> | null = null
    server.use(
      http.get(`${API}/speakers`, () => HttpResponse.json(page([speaker], 1, 1, 50))),
      http.post(`${API}/events/${event.id}/sessions`, async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>
        const created = makeSession({
          id: 'new',
          title: 'Charla nueva',
          speaker: { id: 'sp-1', name: 'Marta Díaz', bio: null },
        })
        state.sessions = [created]
        return HttpResponse.json(created, { status: 201 })
      }),
    )
    setAuthenticated(makeUserWithRole('organizer', { id: 'owner-1' }))
    const { user } = open(event)

    await user.click(await screen.findByRole('button', { name: /agregar sesión/i }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Título'), 'Charla nueva')
    await user.click(within(dialog).getByRole('combobox', { name: 'Ponente' }))
    await user.click(await screen.findByRole('option', { name: 'Marta Díaz' }))
    await user.click(within(dialog).getByRole('button', { name: 'Crear sesión' }))

    expect(await screen.findByText('Sesión creada')).toBeInTheDocument()
    expect(posted).toMatchObject({ speaker_id: 'sp-1', title: 'Charla nueva', capacity: 30 })
    expect(await screen.findByText('Charla nueva')).toBeInTheDocument()
  })

  it('valida en el formulario que la sesión esté dentro del horario del evento', async () => {
    const event = makeEvent({ organizer_id: 'owner-1', capacity: 100 })
    backend({ event })
    server.use(
      http.get(`${API}/speakers`, () =>
        HttpResponse.json(page([makeSpeaker({ id: 'sp-1', name: 'Marta' })], 1, 1, 50)),
      ),
    )
    setAuthenticated(makeUserWithRole('organizer', { id: 'owner-1' }))
    const { user } = open(event)

    await user.click(await screen.findByRole('button', { name: /agregar sesión/i }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Título'), 'Fuera de hora')
    await user.click(within(dialog).getByRole('combobox', { name: 'Ponente' }))
    await user.click(await screen.findByRole('option', { name: 'Marta' }))
    const start = within(dialog).getByLabelText('Inicio')
    await user.clear(start)
    await user.type(start, '2029-01-01T10:00')
    await user.click(within(dialog).getByRole('button', { name: 'Crear sesión' }))

    expect(
      await within(dialog).findByText('La sesión debe estar dentro del horario del evento'),
    ).toBeInTheDocument()
  })
})
