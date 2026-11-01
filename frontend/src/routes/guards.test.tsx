import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { API } from '@/test/handlers'
import { makeSpeaker, makeUser, makeUserWithRole, page } from '@/test/factories'
import { server } from '@/test/server'
import { mockSession, renderApp } from '@/test/utils'

describe('rutas protegidas', () => {
  it('un anónimo que abre /profile va a /login y vuelve a /profile tras ingresar', async () => {
    const { user, router } = renderApp('/profile')

    expect(await screen.findByRole('heading', { name: 'Ingresar' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')

    const me = makeUser({ full_name: 'Ana Pérez' })
    server.use(
      http.post(`${API}/auth/login`, () => HttpResponse.json(me)),
      http.get(`${API}/users/me/registrations`, () => HttpResponse.json([])),
    )
    await user.type(screen.getByLabelText('Correo'), me.email)
    await user.type(screen.getByLabelText('Contraseña'), 'secreto123')
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByRole('heading', { name: 'Mi perfil' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/profile')
  })

  it('un asistente no entra a las secciones de gestión', async () => {
    mockSession(makeUserWithRole('attendee'))
    renderApp('/speakers')

    expect(await screen.findByText('No tienes acceso a esta sección')).toBeInTheDocument()
  })

  it('un organizador sí entra a Ponentes', async () => {
    mockSession(makeUserWithRole('organizer'))
    server.use(
      http.get(`${API}/speakers`, () =>
        HttpResponse.json(page([makeSpeaker({ name: 'Luis Gómez' })])),
      ),
    )
    renderApp('/speakers')

    expect(await screen.findByText('Luis Gómez')).toBeInTheDocument()
  })

  it('solo el administrador entra a Usuarios', async () => {
    mockSession(makeUserWithRole('organizer'))
    renderApp('/admin/users')
    expect(await screen.findByText('No tienes acceso a esta sección')).toBeInTheDocument()
  })

  it('quien ya inició sesión no ve el login: vuelve al inicio', async () => {
    mockSession(makeUser())
    const { router } = renderApp('/login')

    await screen.findByRole('heading', { name: /descubre eventos/i })
    expect(router.state.location.pathname).toBe('/')
  })

  it('una dirección inexistente muestra la página 404', async () => {
    renderApp('/no-existe')
    expect(await screen.findByText('Página no encontrada')).toBeInTheDocument()
  })

  it('mientras se restaura la sesión no se redirige prematuramente', async () => {
    server.use(
      http.get(`${API}/auth/me`, async () => {
        await new Promise((r) => setTimeout(r, 80))
        return HttpResponse.json(makeUser({ full_name: 'Lenta' }))
      }),
    )
    const { router } = renderApp('/profile')

    expect(router.state.location.pathname).toBe('/profile') // sigue esperando
    server.use(http.get(`${API}/users/me/registrations`, () => HttpResponse.json([])))
    expect(await screen.findByRole('heading', { name: 'Mi perfil' })).toBeInTheDocument()
  })
})

describe('navegación según el rol', () => {
  it('el administrador ve todos los enlaces de gestión', async () => {
    mockSession(makeUserWithRole('admin'))
    renderApp('/')

    const nav = await screen.findByRole('navigation', { name: 'Principal' })
    expect(await screen.findByRole('button', { name: 'Menú de usuario' })).toBeInTheDocument()
    for (const label of ['Eventos', 'Crear evento', 'Ponentes', 'Usuarios']) {
      expect(nav).toHaveTextContent(label)
    }
  })

  it('el asistente solo ve Eventos', async () => {
    mockSession(makeUserWithRole('attendee'))
    renderApp('/')

    await screen.findByRole('button', { name: 'Menú de usuario' })
    const nav = screen.getByRole('navigation', { name: 'Principal' })
    expect(nav).toHaveTextContent('Eventos')
    expect(nav).not.toHaveTextContent('Crear evento')
    expect(nav).not.toHaveTextContent('Usuarios')
  })

  it('el anónimo ve Ingresar y Crear cuenta', async () => {
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Ingresar' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Crear cuenta' })).toBeInTheDocument()
  })
})
