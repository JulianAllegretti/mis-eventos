import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import EventListPage from '@/pages/EventListPage'
import { API } from '@/test/handlers'
import { makeEvent, makeUserWithRole, page } from '@/test/factories'
import { server } from '@/test/server'
import { renderPage, setAnonymous, setAuthenticated } from '@/test/utils'

type Query = Record<string, string>
let queries: Query[] = []

function serve(
  events = [makeEvent({ name: 'Congreso de Python' }), makeEvent({ name: 'Taller de Rust' })],
  total?: number,
) {
  server.use(
    http.get(`${API}/events`, ({ request }) => {
      queries.push(Object.fromEntries(new URL(request.url).searchParams))
      return HttpResponse.json(page(events, total ?? events.length))
    }),
  )
}

const open = (url = '/') => renderPage(<EventListPage />, { path: '/', url })

describe('EventListPage', () => {
  beforeEach(() => {
    queries = []
    setAnonymous()
  })

  it('lista los eventos como tarjetas con enlace al detalle', async () => {
    serve()
    open()

    expect(await screen.findByRole('link', { name: 'Congreso de Python' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Taller de Rust' })).toBeInTheDocument()
    expect(screen.getByText('2 eventos')).toBeInTheDocument()
  })

  it('muestra esqueletos mientras carga', async () => {
    server.use(
      http.get(`${API}/events`, async () => {
        await new Promise((r) => setTimeout(r, 100))
        return HttpResponse.json(page([]))
      }),
    )
    open()

    expect(screen.getByLabelText('Cargando eventos')).toBeInTheDocument()
    await screen.findByText('Aún no hay eventos publicados')
  })

  it('el héroe usa imágenes WebP con varios tamaños (srcset)', () => {
    serve()
    const { container } = open()

    const source = container.querySelector('picture source')
    expect(source).toHaveAttribute('type', 'image/webp')
    expect(source?.getAttribute('srcset')).toMatch(/640w.*1280w.*1920w/)
  })

  it('busca por parte del nombre al dejar de escribir y vuelve a la primera página', async () => {
    serve()
    const { user } = open('/?page=3')
    await screen.findByText('Congreso de Python')

    await user.type(screen.getByLabelText('Buscar por nombre'), 'pyth')

    await waitFor(() => expect(queries.at(-1)).toMatchObject({ q: 'pyth', page: '1' }))
    // no dispara una petición por cada tecla: la búsqueda está "debounced"
    expect(queries.filter((q) => q.q && q.q !== 'pyth')).toHaveLength(0)
  })

  it('filtra por estado', async () => {
    serve()
    const { user } = open()
    await screen.findByText('Congreso de Python')

    await user.click(screen.getByRole('combobox', { name: 'Estado' }))
    await user.click(await screen.findByRole('option', { name: 'Finalizados' }))

    await waitFor(() => expect(queries.at(-1)).toMatchObject({ status: 'finished' }))
  })

  it('pagina los resultados', async () => {
    serve([makeEvent({ name: 'Uno' })], 20)
    const { user } = open()

    expect(await screen.findByText('Página 1 de 3')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /siguiente/i }))

    await waitFor(() => expect(queries.at(-1)).toMatchObject({ page: '2', page_size: '9' }))
  })

  it('lee la página y el filtro desde la URL (se pueden compartir)', async () => {
    serve()
    open('/?q=python&page=2&status=published')

    await waitFor(() =>
      expect(queries[0]).toMatchObject({ q: 'python', page: '2', status: 'published' }),
    )
    expect(screen.getByLabelText('Buscar por nombre')).toHaveValue('python')
  })

  it('sin resultados ofrece limpiar los filtros', async () => {
    serve([])
    const { user } = open('/?q=nada')

    expect(await screen.findByText('Sin resultados')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Limpiar filtros' }))

    await waitFor(() => expect(queries.at(-1)?.q).toBeUndefined())
    expect(screen.getByLabelText('Buscar por nombre')).toHaveValue('')
  })

  it('muestra un error con opción de reintentar', async () => {
    server.use(
      http.get(`${API}/events`, () =>
        HttpResponse.json({ code: 'internal_error', message: 'Error interno' }, { status: 500 }),
      ),
    )
    const { user } = open()

    expect(await screen.findByText('Error interno')).toBeInTheDocument()

    serve([makeEvent({ name: 'Recuperado' })])
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Recuperado')).toBeInTheDocument()
  })

  it('los organizadores ven "Crear evento" y el filtro de sus eventos; los asistentes no', async () => {
    serve()
    setAuthenticated(makeUserWithRole('organizer'))
    const first = open()
    expect(await screen.findByRole('link', { name: /crear evento/i })).toBeInTheDocument()
    expect(screen.getByLabelText('Solo mis eventos')).toBeInTheDocument()
    first.unmount()

    setAuthenticated(makeUserWithRole('attendee'))
    open()
    await screen.findByText('Congreso de Python')
    expect(screen.queryByRole('link', { name: /crear evento/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Solo mis eventos')).not.toBeInTheDocument()
  })

  it('"Solo mis eventos" pide el ámbito mine para ver también los borradores', async () => {
    serve([makeEvent({ name: 'Mi borrador', status: 'draft' })])
    setAuthenticated(makeUserWithRole('organizer'))
    const { user } = open()
    await screen.findByText('Mi borrador')

    await user.click(screen.getByLabelText('Solo mis eventos'))

    await waitFor(() => expect(queries.at(-1)).toMatchObject({ scope: 'mine' }))
    const card = screen.getByRole('link', { name: 'Mi borrador' }).closest('li')!
    expect(within(card).getByText('Borrador')).toBeInTheDocument()
  })
})
