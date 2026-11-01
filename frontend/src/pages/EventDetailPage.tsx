import { CalendarDays, CalendarX2, MapPin, Plus, Users } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { registrationsApi } from '@/api/registrations'
import { sessionsApi } from '@/api/sessions'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageSpinner, Spinner } from '@/components/Spinner'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { AvailabilityBar } from '@/features/events/AvailabilityBar'
import { EventActions } from '@/features/events/EventActions'
import { AttendeesPanel } from '@/features/registrations/AttendeesPanel'
import { SessionFormDialog } from '@/features/sessions/SessionFormDialog'
import { SessionList } from '@/features/sessions/SessionList'
import { useAsyncData } from '@/hooks/useAsyncData'
import { useAuthStore } from '@/stores/authStore'
import { useEventsStore } from '@/stores/eventsStore'
import { useRegistrationsStore } from '@/stores/registrationsStore'
import { formatDateTime } from '@/utils/date'
import { describeError } from '@/utils/errors'

export default function EventDetailPage() {
  const { id = '' } = useParams()
  const location = useLocation()

  const user = useAuthStore((s) => s.user)
  const authStatus = useAuthStore((s) => s.status)
  const {
    current: event,
    currentLoading,
    currentError,
    fetchEvent,
    clearCurrent,
    setCurrent,
  } = useEventsStore()
  const registrations = useRegistrationsStore((s) => s.items)
  const loadRegistrations = useRegistrationsStore((s) => s.load)

  const {
    data: sessionData,
    error: sessionsError,
    reload: loadSessions,
  } = useAsyncData(() => sessionsApi.listForEvent(id), [id])
  const sessions = sessionData ?? []
  const [busy, setBusy] = useState(false)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [sessionDialog, setSessionDialog] = useState(false)
  const [showAttendees, setShowAttendees] = useState(false)

  useEffect(() => {
    void fetchEvent(id)
    return clearCurrent
  }, [id, fetchEvent, clearCurrent])

  useEffect(() => {
    if (authStatus === 'authenticated') void loadRegistrations().catch(() => undefined)
  }, [authStatus, loadRegistrations])

  const refreshAll = useCallback(async () => {
    loadSessions()
    await Promise.all([
      fetchEvent(id),
      authStatus === 'authenticated' ? loadRegistrations().catch(() => undefined) : undefined,
    ])
  }, [id, authStatus, fetchEvent, loadSessions, loadRegistrations])

  const myRegistration = registrations.find((r) => r.event.id === id)
  const registered = Boolean(myRegistration)
  const enrolledIds = useMemo(
    () => new Set(myRegistration?.sessions.map((s) => s.id) ?? []),
    [myRegistration],
  )

  if (currentLoading && !event) return <PageSpinner />
  if (currentError) {
    return currentError.status === 404 ? (
      <EmptyState
        icon={<CalendarX2 />}
        title="Evento no encontrado"
        description="Puede que no exista o que todavía no esté publicado."
        action={
          <Button asChild>
            <Link to="/">Ver eventos</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState error={currentError} onRetry={() => void fetchEvent(id)} />
    )
  }
  if (!event) return null

  const canManage =
    user !== null &&
    (user.role === 'admin' || (user.role === 'organizer' && user.id === event.organizer_id))
  const isOpen = event.status === 'published'
  const isFull = event.available_slots <= 0
  const isEditable = event.status === 'draft' || event.status === 'published'

  async function register() {
    setBusy(true)
    try {
      await registrationsApi.register(id)
      toast.success('¡Listo! Quedaste inscrito al evento')
    } catch (error) {
      toast.error(describeError(error))
    } finally {
      await refreshAll()
      setBusy(false)
    }
  }

  async function cancelRegistration() {
    try {
      await registrationsApi.cancel(id)
      toast.success('Cancelaste tu inscripción')
    } catch (error) {
      toast.error(describeError(error))
    } finally {
      await refreshAll()
    }
  }

  return (
    <div className="space-y-6">
      <nav aria-label="Ruta de navegación" className="text-sm text-muted-foreground">
        <Link to="/" className="hover:text-foreground hover:underline">
          Eventos
        </Link>{' '}
        / <span aria-current="page">{event.name}</span>
      </nav>

      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={event.status} />
          {registered && <Badge variant="success">Estás inscrito</Badge>}
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-balance">{event.name}</h1>
        {canManage && <EventActions event={event} onChanged={setCurrent} />}
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-8">
          {event.description && (
            <section aria-labelledby="about">
              <h2 id="about" className="mb-2 text-lg font-semibold">
                Acerca del evento
              </h2>
              <p className="whitespace-pre-line text-muted-foreground">{event.description}</p>
            </section>
          )}

          <section aria-labelledby="agenda" className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h2 id="agenda" className="text-lg font-semibold">
                Agenda
              </h2>
              {canManage && isEditable && (
                <Button size="sm" onClick={() => setSessionDialog(true)}>
                  <Plus /> Agregar sesión
                </Button>
              )}
            </div>

            {sessionsError ? (
              <ErrorState
                error={sessionsError}
                title="No pudimos cargar la agenda"
                onRetry={loadSessions}
              />
            ) : sessions.length === 0 ? (
              <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                Este evento aún no tiene sesiones programadas.
              </p>
            ) : (
              <>
                {authStatus === 'authenticated' && isOpen && !registered && (
                  <p className="text-sm text-muted-foreground">
                    Inscríbete al evento para poder elegir tus sesiones.
                  </p>
                )}
                <SessionList
                  event={event}
                  sessions={sessions}
                  canEnroll={authStatus === 'authenticated' && isOpen && registered}
                  enrolledIds={enrolledIds}
                  canManage={canManage && isEditable}
                  onChanged={() => void refreshAll()}
                />
              </>
            )}
          </section>

          {canManage && (
            <section aria-labelledby="attendees" className="space-y-3">
              <Separator />
              <div className="flex items-center justify-between gap-3">
                <h2 id="attendees" className="text-lg font-semibold">
                  Asistentes ({event.registered_count})
                </h2>
                <Button variant="outline" size="sm" onClick={() => setShowAttendees((v) => !v)}>
                  <Users /> {showAttendees ? 'Ocultar' : 'Ver asistentes'}
                </Button>
              </div>
              {showAttendees && <AttendeesPanel eventId={event.id} key={event.registered_count} />}
            </section>
          )}
        </div>

        <aside aria-label="Detalles e inscripción">
          <Card className="sticky top-20 gap-4">
            <CardHeader>
              <CardTitle asChild className="text-base">
                <h2>Detalles</h2>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-start gap-3 text-sm">
                <CalendarDays
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <div>
                  <p>{formatDateTime(event.start_at)}</p>
                  <p className="text-muted-foreground">hasta {formatDateTime(event.end_at)}</p>
                </div>
              </div>
              <div className="flex items-start gap-3 text-sm">
                <MapPin className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                <p>{event.location}</p>
              </div>
              <AvailabilityBar registered={event.registered_count} capacity={event.capacity} />

              <Separator />

              {!isOpen ? (
                <p className="text-sm text-muted-foreground">
                  {event.status === 'draft'
                    ? 'Este evento es un borrador: todavía no admite inscripciones.'
                    : event.status === 'cancelled'
                      ? 'Este evento fue cancelado.'
                      : 'Este evento ya finalizó.'}
                </p>
              ) : authStatus === 'unknown' ? (
                <Spinner />
              ) : authStatus === 'anonymous' ? (
                <Button className="w-full" asChild>
                  <Link to="/login" state={{ from: location.pathname }}>
                    Ingresa para inscribirte
                  </Link>
                </Button>
              ) : registered ? (
                <Button variant="outline" className="w-full" onClick={() => setConfirmCancel(true)}>
                  Cancelar inscripción
                </Button>
              ) : (
                <Button className="w-full" disabled={busy || isFull} onClick={register}>
                  {busy && <Spinner className="size-4 text-current" />}
                  {isFull ? 'Sin cupos disponibles' : 'Inscribirme'}
                </Button>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="Cancelar inscripción"
        description="Liberarás tu cupo y también se cancelarán tus inscripciones a las sesiones de este evento."
        confirmLabel="Cancelar inscripción"
        destructive
        onConfirm={cancelRegistration}
      />

      {sessionDialog && (
        <SessionFormDialog
          event={event}
          open
          onOpenChange={(open) => !open && setSessionDialog(false)}
          onSaved={() => void refreshAll()}
        />
      )}
    </div>
  )
}
