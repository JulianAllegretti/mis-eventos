import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { sessionsApi } from '@/api/sessions'
import { speakersApi } from '@/api/speakers'
import type { AgendaSession, AppEvent } from '@/api/types'
import { Spinner } from '@/components/Spinner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  makeSessionSchema,
  sessionToFormValues,
  sessionValuesToInput,
  type SessionFormValues,
} from '@/features/sessions/schemas'
import { useAsyncData } from '@/hooks/useAsyncData'
import { toDatetimeLocal } from '@/utils/date'
import { describeError } from '@/utils/errors'

interface SessionFormDialogProps {
  event: AppEvent
  session?: AgendaSession
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

export function SessionFormDialog({
  event,
  session,
  open,
  onOpenChange,
  onSaved,
}: SessionFormDialogProps) {
  const { data: speakerPage, loading: loadingSpeakers } = useAsyncData(
    () => speakersApi.list({ page_size: 50 }),
    [open],
  )
  const speakers = speakerPage?.items ?? []
  const schema = useMemo(() => makeSessionSchema(event), [event])

  const defaults: SessionFormValues = session
    ? sessionToFormValues(session)
    : {
        speaker_id: '',
        title: '',
        description: '',
        start_at: toDatetimeLocal(event.start_at),
        end_at: toDatetimeLocal(event.end_at),
        capacity: Math.min(event.capacity, 30),
      }

  const form = useForm<SessionFormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults,
  })

  useEffect(() => {
    if (open) form.reset(defaults)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, session?.id])

  async function onSubmit(values: SessionFormValues) {
    try {
      const input = sessionValuesToInput(values)
      if (session) await sessionsApi.update(session.id, input)
      else await sessionsApi.create(event.id, input)
      toast.success(session ? 'Sesión actualizada' : 'Sesión creada')
      onOpenChange(false)
      onSaved()
    } catch (error) {
      toast.error(describeError(error))
    }
  }

  const submitting = form.formState.isSubmitting

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{session ? 'Editar sesión' : 'Nueva sesión'}</DialogTitle>
          <DialogDescription>
            La sesión debe estar dentro del horario del evento y un ponente no puede tener dos a la
            vez.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Título</FormLabel>
                  <FormControl>
                    <Input autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="speaker_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Ponente</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={loadingSpeakers}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue
                          placeholder={loadingSpeakers ? 'Cargando…' : 'Elige un ponente'}
                        />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {speakers.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {!loadingSpeakers && speakers.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      Aún no hay ponentes. Créalos en la sección Ponentes.
                    </p>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="start_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Inicio</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="end_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Fin</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="capacity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Capacidad</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      {...field}
                      value={Number.isNaN(field.value) ? '' : field.value}
                      onChange={(e) => field.onChange(e.target.valueAsNumber)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Descripción (opcional)</FormLabel>
                  <FormControl>
                    <Textarea rows={3} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting && <Spinner className="size-4 text-current" />}
                {session ? 'Guardar cambios' : 'Crear sesión'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
