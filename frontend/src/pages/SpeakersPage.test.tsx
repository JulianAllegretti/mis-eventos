import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { Speaker } from '@/api/types'
import SpeakersPage from '@/pages/SpeakersPage'
import { API } from '@/test/handlers'
import { makeSpeaker, makeUserWithRole, page } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage, setAuthenticated } from '@/test/utils'

const open = () => renderPage(<SpeakersPage />, { path: '/speakers', url: '/speakers' })

function serve(initial: Speaker[]) {
  let items = initial
  const requests: { method: string; url: string; body?: unknown }[] = []
  server.use(
    http.get(`${API}/speakers`, ({ request }) => {
      const q = new URL(request.url).searchParams.get('q')?.toLowerCase()
      requests.push({ method: 'GET', url: request.url })
      const filtered = q ? items.filter((s) => s.name.toLowerCase().includes(q)) : items
      return HttpResponse.json(page(filtered, filtered.length, 1, 10))
    }),
    http.post(`${API}/speakers`, async ({ request }) => {
      const body = (await request.json()) as Partial<Speaker>
      requests.push({ method: 'POST', url: request.url, body })
      const created = makeSpeaker({ ...body, name: body.name! })
      items = [...items, created]
      return HttpResponse.json(created, { status: 201 })
    }),
    http.patch(`${API}/speakers/:id`, async ({ request, params }) => {
      const body = (await request.json()) as Partial<Speaker>
      requests.push({ method: 'PATCH', url: request.url, body })
      items = items.map((s) => (s.id === params.id ? { ...s, ...body } : s))
      return HttpResponse.json(items.find((s) => s.id === params.id))
    }),
    http.delete(`${API}/speakers/:id`, ({ request, params }) => {
      requests.push({ method: 'DELETE', url: request.url })
      items = items.filter((s) => s.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return requests
}

describe('SpeakersPage', () => {
  beforeEach(() => setAuthenticated(makeUserWithRole('organizer')))

  it('lista los ponentes', async () => {
    serve([
      makeSpeaker({ name: 'Ana Pérez', email: 'ana@x.co' }),
      makeSpeaker({ name: 'Luis Gómez', email: null }),
    ])
    open()

    expect(await screen.findByText('Ana Pérez')).toBeInTheDocument()
    expect(screen.getByText('Luis Gómez')).toBeInTheDocument()
    expect(screen.getByText('ana@x.co')).toBeInTheDocument()
  })

  it('muestra un estado vacío con orientación', async () => {
    serve([])
    open()
    expect(await screen.findByText('Aún no hay ponentes')).toBeInTheDocument()
  })

  it('busca por nombre', async () => {
    serve([makeSpeaker({ name: 'Ana Pérez' }), makeSpeaker({ name: 'Luis Gómez' })])
    const { user } = open()
    await screen.findByText('Ana Pérez')

    await user.type(screen.getByLabelText('Buscar por nombre'), 'luis')

    await waitFor(() => expect(screen.queryByText('Ana Pérez')).not.toBeInTheDocument())
    expect(screen.getByText('Luis Gómez')).toBeInTheDocument()
  })

  it('crea un ponente sin necesidad de cuenta de usuario', async () => {
    const requests = serve([])
    const { user } = open()

    await user.click(await screen.findByRole('button', { name: /nuevo ponente/i }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Nombre'), 'Marta Díaz')
    await user.type(within(dialog).getByLabelText('Biografía (opcional)'), 'Ingeniera de software')
    await user.click(within(dialog).getByRole('button', { name: 'Crear ponente' }))

    expect(await screen.findByText('Ponente creado')).toBeInTheDocument()
    expect(requests.find((r) => r.method === 'POST')?.body).toEqual({
      name: 'Marta Díaz',
      email: null,
      bio: 'Ingeniera de software',
    })
    expect(await screen.findByText('Marta Díaz')).toBeInTheDocument()
  })

  it('valida el nombre y el correo del formulario', async () => {
    serve([])
    const { user } = open()

    await user.click(await screen.findByRole('button', { name: /nuevo ponente/i }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Correo (opcional)'), 'no-es-correo')
    await user.click(within(dialog).getByRole('button', { name: 'Crear ponente' }))

    expect(await within(dialog).findByText('El nombre es obligatorio')).toBeInTheDocument()
    expect(within(dialog).getByText('Correo inválido')).toBeInTheDocument()
  })

  it('edita un ponente con sus datos precargados', async () => {
    const speaker = makeSpeaker({ id: 'sp1', name: 'Ana Pérez', bio: 'Bio vieja' })
    const requests = serve([speaker])
    const { user } = open()

    await user.click(await screen.findByRole('button', { name: 'Editar Ana Pérez' }))
    const dialog = await screen.findByRole('dialog')
    const bio = within(dialog).getByLabelText('Biografía (opcional)')
    expect(bio).toHaveValue('Bio vieja')
    await user.clear(bio)
    await user.type(bio, 'Bio nueva')
    await user.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }))

    expect(await screen.findByText('Ponente actualizado')).toBeInTheDocument()
    expect(requests.find((r) => r.method === 'PATCH')?.body).toMatchObject({ bio: 'Bio nueva' })
  })

  it('elimina un ponente tras confirmar', async () => {
    const requests = serve([makeSpeaker({ id: 'sp1', name: 'Ana Pérez' })])
    const { user } = open()

    await user.click(await screen.findByRole('button', { name: 'Eliminar Ana Pérez' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Eliminar' }))

    expect(await screen.findByText('Ponente eliminado')).toBeInTheDocument()
    expect(requests.some((r) => r.method === 'DELETE')).toBe(true)
    await waitFor(() => expect(screen.queryByText('Ana Pérez')).not.toBeInTheDocument())
  })

  it('explica por qué no se puede eliminar a un ponente con sesiones', async () => {
    serve([makeSpeaker({ id: 'sp1', name: 'Ana Pérez' })])
    server.use(
      http.delete(`${API}/speakers/sp1`, () =>
        HttpResponse.json(
          { code: 'conflict', message: 'El ponente tiene sesiones asignadas' },
          { status: 409 },
        ),
      ),
    )
    const { user } = open()

    await user.click(await screen.findByRole('button', { name: 'Eliminar Ana Pérez' }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Eliminar' }),
    )

    expect(await screen.findByText('El ponente tiene sesiones asignadas')).toBeInTheDocument()
    expect(screen.getByText('Ana Pérez')).toBeInTheDocument()
  })
})
