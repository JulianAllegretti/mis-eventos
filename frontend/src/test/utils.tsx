import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import type { ReactElement } from 'react'
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from 'react-router-dom'
import type { User } from '@/api/types'
import { Toaster } from '@/components/ui/sonner'
import { routes } from '@/routes'
import { useAuthStore } from '@/stores/authStore'
import { server } from '@/test/server'
import { API } from '@/test/handlers'

/** Simula una sesión abierta (GET /auth/me responde con el usuario). */
export function mockSession(user: User) {
  server.use(http.get(`${API}/auth/me`, () => HttpResponse.json(user)))
}

/** Para pruebas de una sola página: deja el store como si la sesión ya estuviera restaurada. */
export function setAuthenticated(user: User) {
  useAuthStore.setState({ user, status: 'authenticated' })
}

export function setAnonymous() {
  useAuthStore.setState({ user: null, status: 'anonymous' })
}

/** Renderiza una página dentro de un router, con la ruta `path` y la URL inicial `url`. */
export function renderPage(
  ui: ReactElement,
  { path = '/', url = '/' }: { path?: string; url?: string } = {},
) {
  return {
    user: userEvent.setup(),
    ...render(
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path={path} element={ui} />
          <Route path="*" element={<p>otra-ruta</p>} />
        </Routes>
        <Toaster />
      </MemoryRouter>,
    ),
  }
}

/** Renderiza la aplicación completa (layout, guardas y rutas reales) en la URL indicada. */
export function renderApp(url = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [url] })
  return { user: userEvent.setup(), router, ...render(<RouterProvider router={router} />) }
}
