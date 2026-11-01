import { Ban, CheckCheck, Pencil, Rocket, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { eventsApi } from '@/api/events'
import type { AppEvent } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { describeError } from '@/utils/errors'

type Action = 'publish' | 'finish' | 'cancel' | 'delete'

const COPY: Record<
  Action,
  { title: string; description: string; confirm: string; success: string }
> = {
  publish: {
    title: 'Publicar evento',
    description: 'Será visible para todos y se abrirán las inscripciones.',
    confirm: 'Publicar',
    success: 'Evento publicado',
  },
  finish: {
    title: 'Finalizar evento',
    description: 'Se cerrará antes de su hora de fin y dejará de aceptar inscripciones.',
    confirm: 'Finalizar',
    success: 'Evento finalizado',
  },
  cancel: {
    title: 'Cancelar evento',
    description: 'El evento quedará cancelado y no admitirá más cambios ni inscripciones.',
    confirm: 'Cancelar evento',
    success: 'Evento cancelado',
  },
  delete: {
    title: 'Borrar evento',
    description:
      'Se borrará definitivamente junto con su agenda. Solo es posible si nunca tuvo inscripciones.',
    confirm: 'Borrar',
    success: 'Evento borrado',
  },
}

interface EventActionsProps {
  event: AppEvent
  onChanged: (event: AppEvent) => void
}

/** Acciones del organizador (o admin) sobre un evento, según su estado. */
export function EventActions({ event, onChanged }: EventActionsProps) {
  const navigate = useNavigate()
  const [pending, setPending] = useState<Action | null>(null)

  const canEdit = event.status === 'draft' || event.status === 'published'

  async function run(action: Action) {
    try {
      if (action === 'delete') {
        await eventsApi.remove(event.id)
        toast.success(COPY.delete.success)
        navigate('/')
        return
      }
      const updated = await eventsApi[action](event.id)
      toast.success(COPY[action].success)
      onChanged(updated)
    } catch (error) {
      toast.error(describeError(error))
    }
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {canEdit && (
          <Button variant="outline" size="sm" asChild>
            <Link to={`/events/${event.id}/edit`}>
              <Pencil /> Editar
            </Link>
          </Button>
        )}
        {event.status === 'draft' && (
          <Button size="sm" onClick={() => setPending('publish')}>
            <Rocket /> Publicar
          </Button>
        )}
        {event.status === 'published' && (
          <Button variant="secondary" size="sm" onClick={() => setPending('finish')}>
            <CheckCheck /> Finalizar
          </Button>
        )}
        {canEdit && (
          <Button variant="outline" size="sm" onClick={() => setPending('cancel')}>
            <Ban /> Cancelar evento
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="text-destructive"
          onClick={() => setPending('delete')}
        >
          <Trash2 /> Borrar
        </Button>
      </div>

      {pending && (
        <ConfirmDialog
          open
          onOpenChange={(open) => !open && setPending(null)}
          title={COPY[pending].title}
          description={COPY[pending].description}
          confirmLabel={COPY[pending].confirm}
          destructive={pending === 'cancel' || pending === 'delete'}
          onConfirm={() => run(pending)}
        />
      )}
    </>
  )
}
