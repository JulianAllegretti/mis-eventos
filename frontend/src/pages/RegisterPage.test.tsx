import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import RegisterPage from '@/pages/RegisterPage'
import { useAuthStore } from '@/stores/authStore'
import { API } from '@/test/handlers'
import { makeUser } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage } from '@/test/utils'

const open = () => renderPage(<RegisterPage />, { path: '/register', url: '/register' })

async function fill(user: ReturnType<typeof open>['user'], values: Record<string, string>) {
  for (const [label, value] of Object.entries(values)) {
    await user.type(screen.getByLabelText(label), value)
  }
}

describe('RegisterPage', () => {
  it('exige todos los campos', async () => {
    const { user } = open()
    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(await screen.findByText('Escribe tu nombre')).toBeInTheDocument()
    expect(screen.getByText('Escribe un correo válido')).toBeInTheDocument()
    expect(screen.getByText('La contraseña debe tener al menos 8 caracteres')).toBeInTheDocument()
  })

  it('rechaza contraseñas cortas y que no coinciden', async () => {
    const { user } = open()
    await fill(user, {
      'Nombre completo': 'Ana',
      Correo: 'ana@example.com',
      Contraseña: 'corta',
      'Repite la contraseña': 'otra',
    })
    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(
      await screen.findByText('La contraseña debe tener al menos 8 caracteres'),
    ).toBeInTheDocument()
    expect(screen.getByText('Las contraseñas no coinciden')).toBeInTheDocument()
  })

  it('no envía la confirmación de contraseña al servidor', async () => {
    let body: Record<string, unknown> = {}
    const me = makeUser()
    server.use(
      http.post(`${API}/auth/register`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(me, { status: 201 })
      }),
      http.post(`${API}/auth/login`, () => HttpResponse.json(me)),
    )
    const { user } = open()

    await fill(user, {
      'Nombre completo': 'Ana Pérez',
      Correo: 'ana@example.com',
      Contraseña: 'secreto123',
      'Repite la contraseña': 'secreto123',
    })
    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'))
    expect(body).toEqual({
      full_name: 'Ana Pérez',
      email: 'ana@example.com',
      password: 'secreto123',
    })
    expect(body).not.toHaveProperty('confirm')
  })

  it('muestra el error si el correo ya está registrado', async () => {
    server.use(
      http.post(`${API}/auth/register`, () =>
        HttpResponse.json(
          {
            code: 'email_already_registered',
            message: 'El correo ya está registrado',
            details: [],
          },
          { status: 409 },
        ),
      ),
    )
    const { user } = open()
    await fill(user, {
      'Nombre completo': 'Ana',
      Correo: 'ana@example.com',
      Contraseña: 'secreto123',
      'Repite la contraseña': 'secreto123',
    })
    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('El correo ya está registrado')
  })
})
