import { CalendarCheck2, Clock, Mic } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { registrationsApi } from '@/api/registrations'
import { sessionsApi } from '@/api/sessions'
import type { MyRegistration } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuthStore } from '@/stores/authStore'
import { useRegistrationsStore } from '@/stores/registrationsStore'
import { formatDateTime, formatRange, formatTime } from '@/utils/date'
import { describeError } from '@/utils/errors'

const ROLE_LABEL = {
  attendee: 'Asistente',
  organizer: 'Organizador',
  admin: 'Administrador',
} as const

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user)
  const { items, loaded, loading, load } = useRegistrationsStore()
  const [error, setError] = useState<unknown>(null)
  const [cancelling, setCancelling] = useState<MyRegistration | null>(null)

  useEffect(() => {
    load().catch(setError)
  }, [load])

  async function cancelEvent(registration: MyRegistration) {
    try {
      await registrationsApi.cancel(registration.event.id)
      toast.success('Cancelaste tu inscripción')
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      await load().catch(() => undefined)
    }
  }

  async function cancelSession(sessionId: string) {
    try {
      await sessionsApi.cancelRegistration(sessionId)
      toast.success('Cancelaste tu inscripción a la sesión')
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      await load().catch(() => undefined)
    }
  }

  if (!user) return null

  return (
    <div className="space-y-8">
      <PageHeader title="Mi perfil" />

      <Card className="gap-3">
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-lg font-semibold">{user.full_name}</p>
            <p className="text-sm text-muted-foreground">{user.email}</p>
          </div>
          <Badge variant="secondary">{ROLE_LABEL[user.role]}</Badge>
        </CardContent>
      </Card>

      <section aria-labelledby="my-registrations" className="space-y-4">
        <h2 id="my-registrations" className="text-xl font-semibold">
          Mis inscripciones
        </h2>

        {error ? (
          <ErrorState
            error={error}
            onRetry={() =>
              load()
                .then(() => setError(null))
                .catch(setError)
            }
          />
        ) : !loaded && loading ? (
          <div className="space-y-3">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-28 w-full" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<CalendarCheck2 />}
            title="Aún no estás inscrito a ningún evento"
            description="Explora los eventos disponibles e inscríbete."
            action={
              <Button asChild>
                <Link to="/">Ver eventos</Link>
              </Button>
            }
          />
        ) : (
          <ul className="space-y-4">
            {items.map((registration) => (
              <li key={registration.event.id}>
                <Card className="gap-4">
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <CardTitle asChild className="text-lg">
                          <h3>
                            <Link
                              to={`/events/${registration.event.id}`}
                              className="hover:underline"
                            >
                              {registration.event.name}
                            </Link>
                          </h3>
                        </CardTitle>
                        <p className="text-sm text-muted-foreground">
                          {formatRange(registration.event.start_at, registration.event.end_at)} ·{' '}
                          {registration.event.location}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Inscrito el {formatDateTime(registration.registered_at)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={registration.event.status} />
                        {registration.event.status === 'published' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCancelling(registration)}
                          >
                            Cancelar inscripción
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  {registration.sessions.length > 0 && (
                    <CardContent>
                      <h3 className="mb-2 text-sm font-medium">Mis sesiones</h3>
                      <ul className="divide-y rounded-lg border">
                        {registration.sessions.map((session) => (
                          <li
                            key={session.id}
                            className="flex flex-wrap items-center justify-between gap-2 p-3"
                          >
                            <div className="space-y-0.5">
                              <p className="text-sm font-medium">{session.title}</p>
                              <p className="flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
                                <span className="inline-flex items-center gap-1">
                                  <Clock className="size-3.5" aria-hidden />
                                  {formatDateTime(session.start_at)} – {formatTime(session.end_at)}
                                </span>
                                {session.speaker && (
                                  <span className="inline-flex items-center gap-1">
                                    <Mic className="size-3.5" aria-hidden />
                                    {session.speaker.name}
                                  </span>
                                )}
                              </p>
                            </div>
                            {registration.event.status === 'published' && (
                              <Button
                                variant="ghost"
                                size="sm"
                                aria-label={`Cancelar inscripción a ${session.title}`}
                                onClick={() => void cancelSession(session.id)}
                              >
                                Cancelar
                              </Button>
                            )}
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      {cancelling && (
        <ConfirmDialog
          open
          onOpenChange={(open) => !open && setCancelling(null)}
          title="Cancelar inscripción"
          description={`Liberarás tu cupo en «${cancelling.event.name}» y se cancelarán tus sesiones de ese evento.`}
          confirmLabel="Cancelar inscripción"
          destructive
          onConfirm={() => cancelEvent(cancelling)}
        />
      )}
    </div>
  )
}
