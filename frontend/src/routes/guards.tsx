import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { Role } from '@/api/types'
import { PageSpinner } from '@/components/Spinner'
import ForbiddenPage from '@/pages/ForbiddenPage'
import { useAuthStore } from '@/stores/authStore'

/** Exige sesión (y opcionalmente uno de los roles indicados). */
export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const status = useAuthStore((s) => s.status)
  const user = useAuthStore((s) => s.user)
  const location = useLocation()

  if (status === 'unknown') return <PageSpinner />
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  if (roles && user && !roles.includes(user.role)) return <ForbiddenPage />
  return <Outlet />
}

/** Para login y registro: quien ya tiene sesión vuelve al inicio. */
export function GuestRoute() {
  const status = useAuthStore((s) => s.status)
  if (status === 'unknown') return <PageSpinner />
  if (status === 'authenticated') return <Navigate to="/" replace />
  return <Outlet />
}
