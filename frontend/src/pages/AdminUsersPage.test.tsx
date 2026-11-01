import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { User } from '@/api/types'
import AdminUsersPage from '@/pages/AdminUsersPage'
import { API } from '@/test/handlers'
import { makeUser, makeUserWithRole, page } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage, setAuthenticated } from '@/test/utils'

const open = () => renderPage(<AdminUsersPage />, { path: '/admin/users', url: '/admin/users' })

function serve(users: User[]) {
  const patches: { id: string; body: Record<string, unknown> }[] = []
  server.use(
    http.get(`${API}/admin/users`, ({ request }) => {
      const q = new URL(request.url).searchParams.get('q')?.toLowerCase()
      const filtered = q
        ? users.filter((u) => u.email.includes(q) || u.full_name.toLowerCase().includes(q))
        : users
      return HttpResponse.json(page(filtered, filtered.length, 1, 10))
    }),
    http.patch(`${API}/admin/users/:id`, async ({ request, params }) => {
      const body = (await request.json()) as Record<string, unknown>
      patches.push({ id: String(params.id), body })
      const user = users.find((u) => u.id === params.id)!
      return HttpResponse.json({ ...user, ...body })
    }),
  )
  return patches
}

describe('AdminUsersPage', () => {
  const me = makeUserWithRole('admin', {
    id: 'admin-1',
    full_name: 'Admin Root',
    email: 'admin@example.com',
  })
  const ana = makeUser({ id: 'u1', full_name: 'Ana Pérez', email: 'ana@example.com' })

  beforeEach(() => setAuthenticated(me))

  it('lista los usuarios con su rol y estado', async () => {
    serve([me, ana])
    open()

    expect(await screen.findByText('Ana Pérez')).toBeInTheDocument()
    expect(screen.getByText('ana@example.com')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Rol de Ana Pérez' })).toHaveTextContent(
      'Asistente',
    )
    expect(screen.getByRole('switch', { name: 'Cuenta activa de Ana Pérez' })).toBeChecked()
  })

  it('un administrador no puede cambiarse a sí mismo (evita quedarse sin acceso)', async () => {
    serve([me, ana])
    open()

    await screen.findByText('Ana Pérez')
    expect(screen.getByText('(tú)')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Rol de Admin Root' })).toBeDisabled()
    expect(screen.getByRole('switch', { name: 'Cuenta activa de Admin Root' })).toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'Rol de Ana Pérez' })).toBeEnabled()
  })

  it('cambia el rol de un usuario', async () => {
    const patches = serve([me, ana])
    const { user } = open()

    await user.click(await screen.findByRole('combobox', { name: 'Rol de Ana Pérez' }))
    await user.click(await screen.findByRole('option', { name: 'Organizador' }))

    expect(await screen.findByText('Usuario actualizado')).toBeInTheDocument()
    expect(patches).toEqual([{ id: 'u1', body: { role: 'organizer' } }])
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: 'Rol de Ana Pérez' })).toHaveTextContent(
        'Organizador',
      ),
    )
  })

  it('desactiva una cuenta', async () => {
    const patches = serve([me, ana])
    const { user } = open()

    await user.click(await screen.findByRole('switch', { name: 'Cuenta activa de Ana Pérez' }))

    await waitFor(() => expect(patches).toEqual([{ id: 'u1', body: { is_active: false } }]))
    await waitFor(() =>
      expect(screen.getByRole('switch', { name: 'Cuenta activa de Ana Pérez' })).not.toBeChecked(),
    )
  })

  it('muestra el error del servidor y conserva el valor anterior', async () => {
    serve([me, ana])
    server.use(
      http.patch(`${API}/admin/users/u1`, () =>
        HttpResponse.json(
          { code: 'forbidden', message: 'No tienes permiso para realizar esta acción' },
          { status: 403 },
        ),
      ),
    )
    const { user } = open()

    await user.click(await screen.findByRole('switch', { name: 'Cuenta activa de Ana Pérez' }))

    expect(
      await screen.findByText('No tienes permiso para realizar esta acción'),
    ).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Cuenta activa de Ana Pérez' })).toBeChecked()
  })

  it('busca por correo o nombre', async () => {
    serve([me, ana])
    const { user } = open()
    await screen.findByText('Ana Pérez')

    await user.type(screen.getByLabelText('Buscar por correo o nombre'), 'ana@')

    await waitFor(() => expect(screen.queryByText('Admin Root')).not.toBeInTheDocument())
    expect(within(screen.getByRole('table')).getByText('Ana Pérez')).toBeInTheDocument()
  })

  it('sin resultados lo indica', async () => {
    serve([])
    open()
    expect(await screen.findByText('Sin resultados')).toBeInTheDocument()
  })
})
