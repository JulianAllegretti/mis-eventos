import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { SessionList } from '@/features/sessions/SessionList'
import { API } from '@/test/handlers'
import { makeEvent, makeSession, makeSpeaker, page } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage } from '@/test/utils'

const event = makeEvent({ id: 'e1', capacity: 100 })

function open(props: Partial<React.ComponentProps<typeof SessionList>> = {}) {
  const onChanged = vi.fn()
  const sessions = [
    makeSession({ id: 's1', title: 'Introducción', capacity: 30, registered_count: 4 }),
  ]
  return {
    onChanged,
    ...renderPage(
      <SessionList
        event={event}
        sessions={sessions}
        canEnroll={false}
        enrolledIds={new Set()}
        canManage
        onChanged={onChanged}
        {...props}
      />,
    ),
  }
}

describe('SessionList (gestión)', () => {
  it('muestra horario, ponente y ocupación', () => {
    open({ canManage: false })

    expect(screen.getByText('Introducción')).toBeInTheDocument()
    expect(screen.getByText('Ana Pérez')).toBeInTheDocument()
    expect(screen.getByText('4/30')).toBeInTheDocument()
  })

  it('quien no gestiona ni se inscribe no ve botones', () => {
    open({ canManage: false, canEnroll: false })
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('elimina una sesión tras confirmar y avisa para recargar la agenda', async () => {
    let deleted = false
    server.use(
      http.delete(
        `${API}/sessions/s1`,
        () => ((deleted = true), new HttpResponse(null, { status: 204 })),
      ),
    )
    const { user, onChanged } = open()

    await user.click(screen.getByRole('button', { name: 'Eliminar Introducción' }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Eliminar' }),
    )

    expect(await screen.findByText('Sesión eliminada')).toBeInTheDocument()
    expect(deleted).toBe(true)
    expect(onChanged).toHaveBeenCalled()
  })

  it('no permite eliminar una sesión con inscritos: muestra el motivo', async () => {
    server.use(
      http.delete(`${API}/sessions/s1`, () =>
        HttpResponse.json(
          { code: 'conflict', message: 'La sesión tiene inscritos' },
          { status: 409 },
        ),
      ),
    )
    const { user, onChanged } = open()

    await user.click(screen.getByRole('button', { name: 'Eliminar Introducción' }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Eliminar' }),
    )

    expect(await screen.findByText('La sesión tiene inscritos')).toBeInTheDocument()
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('edita una sesión con sus datos precargados', async () => {
    let body: Record<string, unknown> = {}
    server.use(
      http.get(`${API}/speakers`, () =>
        HttpResponse.json(page([makeSpeaker({ id: 'speaker-1', name: 'Ana Pérez' })], 1, 1, 50)),
      ),
      http.patch(`${API}/sessions/s1`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(makeSession({ id: 's1', title: 'Nuevo título' }))
      }),
    )
    const { user, onChanged } = open()

    await user.click(screen.getByRole('button', { name: 'Editar Introducción' }))
    const dialog = await screen.findByRole('dialog')
    const title = within(dialog).getByLabelText('Título')
    expect(title).toHaveValue('Introducción')
    await user.clear(title)
    await user.type(title, 'Nuevo título')
    await waitFor(() =>
      expect(within(dialog).getByRole('combobox', { name: 'Ponente' })).toHaveTextContent(
        'Ana Pérez',
      ),
    )
    await user.click(within(dialog).getByRole('button', { name: 'Guardar cambios' }))

    expect(await screen.findByText('Sesión actualizada')).toBeInTheDocument()
    expect(body).toMatchObject({ title: 'Nuevo título', speaker_id: 'speaker-1', capacity: 30 })
    expect(onChanged).toHaveBeenCalled()
  })
})
