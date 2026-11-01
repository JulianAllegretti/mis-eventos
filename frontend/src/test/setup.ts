import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { useAuthStore } from '@/stores/authStore'
import { useEventsStore } from '@/stores/eventsStore'
import { useRegistrationsStore } from '@/stores/registrationsStore'
import { server } from '@/test/server'

// La primera visita a cada ruta descarga su código (import diferido): con la máquina ocupada
// 1 s no alcanza. Es solo margen de espera; las aserciones no cambian.
configure({ asyncUtilTimeout: 5000 })

// jsdom no implementa varias APIs que usa Radix UI (select, dialog, menús).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

Element.prototype.hasPointerCapture ??= () => false
Element.prototype.setPointerCapture ??= () => {}
Element.prototype.releasePointerCapture ??= () => {}
Element.prototype.scrollIntoView ??= () => {}
window.scrollTo = () => {}

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  // Cada prueba empieza con los stores en su estado inicial.
  useAuthStore.setState({ user: null, status: 'unknown' })
  useEventsStore.setState({
    items: [],
    total: 0,
    page: 1,
    loading: false,
    error: null,
    current: null,
    currentLoading: false,
    currentError: null,
  })
  useRegistrationsStore.setState({ items: [], loaded: false, loading: false })
})
afterAll(() => server.close())
