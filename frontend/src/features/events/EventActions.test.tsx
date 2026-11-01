import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { EventActions } from '@/features/events/EventActions'
import { API } from '@/test/handlers'
import { makeEvent } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage } from '@/test/utils'

const open = (event = makeEvent(), onChanged = vi.fn()) => ({
  onChanged,
  ...renderPage(<EventActions event={event} onChanged={onChanged} />, {
    path: '/events/:id',
    url: `/events/${event.id}`,
  }),
})

async function confirm(
  user: ReturnType<typeof open>['user'],
  trigger: RegExp | string,
  label: string,
) {
  await user.click(screen.getByRole('button', { name: trigger }))
  const dialog = await screen.findByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: label }))
}

describe('EventActions', () => {
  it.each([
    ['draft', ['Editar', 'Publicar', 'Cancelar evento', 'Borrar'], ['Finalizar']],
    ['published', ['Editar', 'Finalizar', 'Cancelar evento', 'Borrar'], ['Publicar']],
    ['finished', ['Borrar'], ['Editar', 'Publicar', 'Finalizar', 'Cancelar evento']],
    ['cancelled', ['Borrar'], ['Editar', 'Publicar', 'Finalizar', 'Cancelar evento']],
  ] as const)('en estado %s ofrece solo las acciones válidas', (status, visible, hidden) => {
    open(makeEvent({ status }))

    for (const name of visible)
      expect(screen.getByRole(name === 'Editar' ? 'link' : 'button', { name })).toBeInTheDocument()
    for (const name of hidden) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name })).not.toBeInTheDocument()
    }
  })

  it.each([
    ['publish', 'Publicar', 'Publicar', 'published', 'Evento publicado', 'draft'],
    ['finish', 'Finalizar', 'Finalizar', 'finished', 'Evento finalizado', 'published'],
    ['cancel', 'Cancelar evento', 'Cancelar evento', 'cancelled', 'Evento cancelado', 'published'],
  ] as const)(
    '%s: pide confirmación, llama a la API y notifica el resultado',
    async (endpoint, trigger, label, newStatus, toast, current) => {
      const event = makeEvent({ id: 'e1', status: current })
      let called = 0
      server.use(
        http.post(`${API}/events/e1/${endpoint}`, () => {
          called += 1
          return HttpResponse.json({ ...event, status: newStatus })
        }),
      )
      const { user, onChanged } = open(event)

      await user.click(screen.getByRole('button', { name: trigger }))
      await screen.findByRole('dialog')
      expect(called).toBe(0) // nada ocurre hasta confirmar
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: label }))

      expect(await screen.findByText(toast)).toBeInTheDocument()
      expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ status: newStatus }))
    },
  )

  it('borrar elimina el evento y vuelve al listado', async () => {
    const event = makeEvent({ id: 'e1' })
    server.use(http.delete(`${API}/events/e1`, () => new HttpResponse(null, { status: 204 })))
    const { user } = open(event)

    await confirm(user, /borrar/i, 'Borrar')

    expect(await screen.findByText('Evento borrado')).toBeInTheDocument()
    expect(await screen.findByText('otra-ruta')).toBeInTheDocument()
  })

  it('"Volver" en la confirmación no ejecuta nada', async () => {
    let called = false
    server.use(http.post(`${API}/events/e1/cancel`, () => ((called = true), HttpResponse.json({}))))
    const { user } = open(makeEvent({ id: 'e1', status: 'published' }))

    await user.click(screen.getByRole('button', { name: 'Cancelar evento' }))
    await user.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Volver' }),
    )

    expect(called).toBe(false)
  })

  it('muestra el error del servidor y no notifica cambios', async () => {
    server.use(
      http.post(`${API}/events/e1/publish`, () =>
        HttpResponse.json(
          {
            code: 'validation_failed',
            message: 'No se puede publicar un evento cuyo inicio ya pasó',
          },
          { status: 422 },
        ),
      ),
    )
    const { user, onChanged } = open(makeEvent({ id: 'e1', status: 'draft' }))

    await confirm(user, 'Publicar', 'Publicar')

    expect(await screen.findByText(/cuyo inicio ya pasó/)).toBeInTheDocument()
    expect(onChanged).not.toHaveBeenCalled()
  })
})
