import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { MyRegistration } from '@/api/types'
import ProfilePage from '@/pages/ProfilePage'
import { API } from '@/test/handlers'
import { makeEvent, makeRegistration, makeSession, makeUser } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage, setAuthenticated } from '@/test/utils'

const open = () => renderPage(<ProfilePage />, { path: '/profile', url: '/profile' })

function serve(initial: MyRegistration[]) {
  let current = initial
  const calls: string[] = []
  server.use(
    http.get(`${API}/users/me/registrations`, () => HttpResponse.json(current)),
    http.delete(`${API}/events/:id/registrations/me`, ({ params }) => {
      calls.push(`cancel-event:${params.id}`)
      current = current.filter((r) => r.event.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
    http.delete(`${API}/sessions/:id/registrations/me`, ({ params }) => {
      calls.push(`cancel-session:${params.id}`)
      current = current.map((r) => ({
        ...r,
        sessions: r.sessions.filter((s) => s.id !== params.id),
      }))
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return calls
}

describe('ProfilePage', () => {
  beforeEach(() =>
    setAuthenticated(
      makeUser({ full_name: 'Ana Pérez', email: 'ana@example.com', role: 'organizer' }),
    ),
  )

  it('muestra los datos de la cuenta y el rol', async () => {
    serve([])
    open()

    expect(screen.getByRole('heading', { name: 'Mi perfil' })).toBeInTheDocument()
    expect(screen.getByText('Ana Pérez')).toBeInTheDocument()
    expect(screen.getByText('ana@example.com')).toBeInTheDocument()
    expect(screen.getByText('Organizador')).toBeInTheDocument()
    await screen.findByText('Aún no estás inscrito a ningún evento')
  })

  it('lista mis eventos con sus sesiones', async () => {
    const event = makeEvent({ id: 'e1', name: 'Congreso de Python', location: 'Cali' })
    serve([makeRegistration(event, [makeSession({ id: 's1', title: 'Introducción a FastAPI' })])])
    open()

    const card = (await screen.findByRole('heading', { name: 'Congreso de Python' })).closest('li')!
    expect(within(card).getByRole('link', { name: 'Congreso de Python' })).toHaveAttribute(
      'href',
      '/events/e1',
    )
    expect(within(card).getByText('Introducción a FastAPI')).toBeInTheDocument()
    expect(within(card).getByText('Ana Pérez')).toBeInTheDocument() // ponente de la sesión
  })

  it('cancela la inscripción a un evento tras confirmar', async () => {
    const calls = serve([makeRegistration(makeEvent({ id: 'e1', name: 'Congreso de Python' }))])
    const { user } = open()

    await user.click(await screen.findByRole('button', { name: 'Cancelar inscripción' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('Congreso de Python')
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar inscripción' }))

    expect(await screen.findByText('Cancelaste tu inscripción')).toBeInTheDocument()
    expect(await screen.findByText('Aún no estás inscrito a ningún evento')).toBeInTheDocument()
    expect(calls).toEqual(['cancel-event:e1'])
  })

  it('cancela solo una sesión y conserva la inscripción al evento', async () => {
    const event = makeEvent({ id: 'e1', name: 'Congreso' })
    const calls = serve([
      makeRegistration(event, [
        makeSession({ id: 's1', title: 'Sesión A' }),
        makeSession({ id: 's2', title: 'Sesión B' }),
      ]),
    ])
    const { user } = open()

    await user.click(await screen.findByRole('button', { name: 'Cancelar inscripción a Sesión A' }))

    await waitFor(() => expect(screen.queryByText('Sesión A')).not.toBeInTheDocument())
    expect(screen.getByText('Sesión B')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Congreso' })).toBeInTheDocument()
    expect(calls).toEqual(['cancel-session:s1'])
  })

  it('un evento finalizado ya no ofrece cancelar', async () => {
    serve([makeRegistration(makeEvent({ status: 'finished' }), [makeSession({ title: 'Pasada' })])])
    open()

    await screen.findByText('Pasada')
    expect(screen.queryByRole('button', { name: /cancelar/i })).not.toBeInTheDocument()
    expect(screen.getByText('Finalizado')).toBeInTheDocument()
  })

  it('muestra un error con reintento si falla la carga', async () => {
    server.use(
      http.get(`${API}/users/me/registrations`, () =>
        HttpResponse.json({ code: 'internal_error', message: 'Error interno' }, { status: 500 }),
      ),
    )
    const { user } = open()
    expect(await screen.findByText('Error interno')).toBeInTheDocument()

    serve([makeRegistration(makeEvent({ name: 'Recuperado' }))])
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('heading', { name: 'Recuperado' })).toBeInTheDocument()
  })
})
