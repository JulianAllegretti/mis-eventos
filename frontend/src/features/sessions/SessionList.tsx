import { Clock, Mic, Pencil, Trash2, Users } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import type { AgendaSession, AppEvent } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SessionFormDialog } from '@/features/sessions/SessionFormDialog'
import { formatDateTime, formatTime } from '@/utils/date'
import { describeError } from '@/utils/errors'

interface SessionListProps {
  event: AppEvent
  sessions: AgendaSession[]
  /** Puede inscribirse: está autenticado, inscrito al evento y el evento admite inscripciones. */
  canEnroll: boolean
  /** Ids de las sesiones en las que el usuario ya está inscrito. */
  enrolledIds: Set<string>
  canManage: boolean
  onChanged: () => void
}

export function SessionList({
  event,
  sessions,
  canEnroll,
  enrolledIds,
  canManage,
  onChanged,
}: SessionListProps) {
  const [busyId, setBusyId] = useState<string | null>(null)
  const [editing, setEditing] = useState<AgendaSession | null>(null)
  const [deleting, setDeleting] = useState<AgendaSession | null>(null)

  async function toggleEnrollment(session: AgendaSession) {
    setBusyId(session.id)
    try {
      if (enrolledIds.has(session.id)) {
        await sessionsApi.cancelRegistration(session.id)
        toast.success('Cancelaste tu inscripción a la sesión')
      } else {
        await sessionsApi.register(session.id)
        toast.success('Te inscribiste a la sesión')
      }
      onChanged()
    } catch (error) {
      toast.error(describeError(error))
      onChanged()
    } finally {
      setBusyId(null)
    }
  }

  async function removeSession(session: AgendaSession) {
    try {
      await sessionsApi.remove(session.id)
      toast.success('Sesión eliminada')
      onChanged()
    } catch (error) {
      toast.error(describeError(error))
    }
  }

  return (
    <>
      <ol className="space-y-3">
        {sessions.map((session) => {
          const enrolled = enrolledIds.has(session.id)
          const full = session.available_slots <= 0
          return (
            <li key={session.id} className="rounded-lg border bg-card p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-1.5">
                  <h3 className="font-semibold">{session.title}</h3>
                  <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <Clock className="size-4" aria-hidden />
                      {formatDateTime(session.start_at)} – {formatTime(session.end_at)}
                    </span>
                    {session.speaker && (
                      <span className="inline-flex items-center gap-1.5">
                        <Mic className="size-4" aria-hidden />
                        {session.speaker.name}
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1.5">
                      <Users className="size-4" aria-hidden />
                      {session.registered_count}/{session.capacity}
                    </span>
                  </p>
                  {session.description && <p className="text-sm">{session.description}</p>}
                </div>

                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {enrolled && <Badge variant="success">Inscrito</Badge>}
                  {!enrolled && full && <Badge variant="destructive">Sin cupos</Badge>}
                  {canEnroll && (enrolled || !full) && (
                    <Button
                      size="sm"
                      variant={enrolled ? 'outline' : 'default'}
                      disabled={busyId === session.id}
                      onClick={() => toggleEnrollment(session)}
                    >
                      {enrolled ? 'Cancelar' : 'Inscribirme'}
                    </Button>
                  )}
                  {canManage && (
                    <>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Editar ${session.title}`}
                        onClick={() => setEditing(session)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="text-destructive"
                        aria-label={`Eliminar ${session.title}`}
                        onClick={() => setDeleting(session)}
                      >
                        <Trash2 />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </li>
          )
        })}
      </ol>

      {editing && (
        <SessionFormDialog
          event={event}
          session={editing}
          open
          onOpenChange={(open) => !open && setEditing(null)}
          onSaved={onChanged}
        />
      )}
      {deleting && (
        <ConfirmDialog
          open
          onOpenChange={(open) => !open && setDeleting(null)}
          title="Eliminar sesión"
          description={`Se eliminará «${deleting.title}». Solo es posible si no tiene inscritos.`}
          confirmLabel="Eliminar"
          destructive
          onConfirm={() => removeSession(deleting)}
        />
      )}
    </>
  )
}
