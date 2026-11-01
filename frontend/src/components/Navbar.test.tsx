import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { useAuthStore } from '@/stores/authStore'
import { API } from '@/test/handlers'
import { makeUserWithRole } from '@/test/factories'
import { server } from '@/test/server'
import { mockSession, renderApp } from '@/test/utils'

describe('Navbar', () => {
  it('muestra el nombre y el rol del usuario en su menú', async () => {
    mockSession(makeUserWithRole('organizer', { full_name: 'Ana Pérez' }))
    const { user } = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Menú de usuario' }))

    expect(await screen.findByText('Organizador')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /mi perfil/i })).toBeInTheDocument()
  })

  it('cerrar sesión llama al backend, limpia el estado y vuelve al inicio', async () => {
    mockSession(makeUserWithRole('attendee'))
    let loggedOut = false
    server.use(
      http.post(
        `${API}/auth/logout`,
        () => ((loggedOut = true), new HttpResponse(null, { status: 204 })),
      ),
    )
    const { user, router } = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Menú de usuario' }))
    await user.click(await screen.findByRole('menuitem', { name: /cerrar sesión/i }))

    expect(await screen.findByText('Sesión cerrada')).toBeInTheDocument()
    expect(loggedOut).toBe(true)
    expect(useAuthStore.getState()).toMatchObject({ user: null, status: 'anonymous' })
    expect(router.state.location.pathname).toBe('/')
    expect(await screen.findByRole('link', { name: 'Ingresar' })).toBeInTheDocument()
  })

  it('"Mi perfil" abre la página de perfil', async () => {
    mockSession(makeUserWithRole('attendee'))
    server.use(http.get(`${API}/users/me/registrations`, () => HttpResponse.json([])))
    const { user, router } = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Menú de usuario' }))
    await user.click(await screen.findByRole('menuitem', { name: /mi perfil/i }))

    expect(await screen.findByRole('heading', { name: 'Mi perfil' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/profile')
  })

  it('el menú móvil lista las secciones según el rol', async () => {
    mockSession(makeUserWithRole('admin'))
    const { user } = renderApp('/')
    await screen.findByRole('button', { name: 'Menú de usuario' })

    await user.click(screen.getByRole('button', { name: 'Abrir navegación' }))

    for (const label of ['Eventos', 'Crear evento', 'Ponentes', 'Usuarios']) {
      expect(await screen.findByRole('menuitem', { name: label })).toBeInTheDocument()
    }
  })

  it('en móvil, quien no ha ingresado encuentra "Ingresar" y "Crear cuenta" en el menú', async () => {
    const { user, router } = renderApp('/')
    await screen.findByRole('link', { name: 'Ingresar' })

    await user.click(screen.getByRole('button', { name: 'Abrir navegación' }))
    expect(await screen.findByRole('menuitem', { name: 'Crear cuenta' })).toBeInTheDocument()
    await user.click(screen.getByRole('menuitem', { name: 'Ingresar' }))

    expect(router.state.location.pathname).toBe('/login')
  })
})
