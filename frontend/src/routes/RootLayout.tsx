import { Suspense, useEffect } from 'react'
import { Outlet, useRouteError } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import { PageSpinner } from '@/components/Spinner'
import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/ui/sonner'
import { useAuthStore } from '@/stores/authStore'

export function RootLayout() {
  const loadSession = useAuthStore((s) => s.loadSession)

  // Restaura la sesión al abrir la app preguntando al backend (la cookie HttpOnly no se puede leer).
  useEffect(() => {
    void loadSession()
  }, [loadSession])

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Saltar al contenido
      </a>
      <Navbar />
      <main id="contenido" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Suspense fallback={<PageSpinner />}>
          <Outlet />
        </Suspense>
      </main>
      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        Mis Eventos · Gestión de eventos, sesiones e inscripciones
      </footer>
      <Toaster />
    </div>
  )
}

/** Se muestra si falla una ruta o no se pudo descargar su código (p. ej. sin conexión). */
export function RouteError() {
  const error = useRouteError()
  console.error(error)
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-bold">Algo salió mal</h1>
      <p className="text-muted-foreground">
        Ocurrió un error inesperado al mostrar esta página. Intenta recargarla.
      </p>
      <Button onClick={() => window.location.reload()}>Recargar</Button>
    </div>
  )
}
