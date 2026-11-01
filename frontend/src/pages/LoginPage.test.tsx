import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import LoginPage from '@/pages/LoginPage'
import { useAuthStore } from '@/stores/authStore'
import { API } from '@/test/handlers'
import { makeUser } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage } from '@/test/utils'

const open = (url = '/login') => renderPage(<LoginPage />, { path: '/login', url })

describe('LoginPage', () => {
  it('es la página principal con un encabezado h1', () => {
    open()
    expect(screen.getByRole('heading', { level: 1, name: 'Ingresar' })).toBeInTheDocument()
  })

  it('valida los campos antes de llamar a la API', async () => {
    const { user } = open()

    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByText('Escribe un correo válido')).toBeInTheDocument()
    expect(screen.getByText('Escribe tu contraseña')).toBeInTheDocument()
  })

  it('rechaza un correo con formato inválido', async () => {
    const { user } = open()
    await user.type(screen.getByLabelText('Correo'), 'no-es-correo')
    await user.type(screen.getByLabelText('Contraseña'), 'x')
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByText('Escribe un correo válido')).toBeInTheDocument()
  })

  it('muestra el error del servidor si las credenciales no son válidas', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json(
          { code: 'invalid_credentials', message: 'Credenciales inválidas', details: [] },
          { status: 401 },
        ),
      ),
    )
    const { user } = open()

    await user.type(screen.getByLabelText('Correo'), 'ana@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'incorrecta')
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Credenciales inválidas')
    expect(useAuthStore.getState().status).toBe('unknown')
  })

  it('envía las credenciales, guarda la sesión y vuelve a la página de origen', async () => {
    const me = makeUser({ full_name: 'Ana Pérez' })
    let body: unknown
    server.use(
      http.post(`${API}/auth/login`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(me)
      }),
    )
    const { user } = renderPage(<LoginPage />, { path: '/login', url: '/login' })

    await user.type(screen.getByLabelText('Correo'), 'ana@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'secreto123')
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    await waitFor(() => expect(useAuthStore.getState().user).toEqual(me))
    expect(body).toEqual({ email: 'ana@example.com', password: 'secreto123' })
    expect(await screen.findByText('otra-ruta')).toBeInTheDocument() // navegó fuera del login
  })

  it('ofrece un enlace para crear cuenta', () => {
    open()
    expect(screen.getByRole('link', { name: 'Regístrate' })).toHaveAttribute('href', '/register')
  })

  it('deshabilita el botón mientras envía', async () => {
    server.use(
      http.post(`${API}/auth/login`, async () => {
        await new Promise((r) => setTimeout(r, 100))
        return HttpResponse.json(makeUser())
      }),
    )
    const { user } = open()
    await user.type(screen.getByLabelText('Correo'), 'ana@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'secreto123')
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(screen.getByRole('button', { name: /ingresar/i })).toBeDisabled()
    await screen.findByText('otra-ruta')
  })
})
