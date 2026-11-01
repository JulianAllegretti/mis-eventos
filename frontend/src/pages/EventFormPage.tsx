import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { eventsApi } from '@/api/events'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { PageSpinner, Spinner } from '@/components/Spinner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  emptyEventForm,
  eventToFormValues,
  formValuesToInput,
  makeEventSchema,
  type EventFormValues,
} from '@/features/events/schemas'
import { useEventsStore } from '@/stores/eventsStore'
import { describeError } from '@/utils/errors'

/** Crear (`/events/new`) y editar (`/events/:id/edit`) un evento. */
export default function EventFormPage() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const { current, currentLoading, currentError, fetchEvent, clearCurrent } = useEventsStore()

  const schema = useMemo(() => makeEventSchema({ requireFutureStart: !isEdit }), [isEdit])
  const form = useForm<EventFormValues>({
    resolver: zodResolver(schema),
    defaultValues: emptyEventForm,
  })

  useEffect(() => {
    if (id) void fetchEvent(id)
    return clearCurrent
  }, [id, fetchEvent, clearCurrent])

  useEffect(() => {
    if (isEdit && current) form.reset(eventToFormValues(current))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, current?.id])

  if (isEdit && currentLoading && !current) return <PageSpinner />
  if (isEdit && currentError)
    return <ErrorState error={currentError} onRetry={() => id && void fetchEvent(id)} />

  const locked = isEdit && current && current.status !== 'draft' && current.status !== 'published'
  if (locked) {
    return (
      <Alert>
        <AlertTitle>Este evento ya no se puede editar</AlertTitle>
        <AlertDescription>
          Los eventos finalizados o cancelados no admiten cambios.{' '}
          <Link to={`/events/${current.id}`} className="font-medium text-primary underline">
            Volver al evento
          </Link>
        </AlertDescription>
      </Alert>
    )
  }

  async function onSubmit(values: EventFormValues) {
    try {
      const input = formValuesToInput(values)
      if (isEdit && id) {
        await eventsApi.update(id, input)
        toast.success('Cambios guardados')
        navigate(`/events/${id}`)
      } else {
        const created = await eventsApi.create(input)
        toast.success('Evento creado como borrador. Agrega sesiones y publícalo cuando esté listo.')
        navigate(`/events/${created.id}`)
      }
    } catch (error) {
      toast.error(describeError(error))
    }
  }

  const submitting = form.formState.isSubmitting

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title={isEdit ? 'Editar evento' : 'Crear evento'}
        description={
          isEdit
            ? 'Los cambios se aplican de inmediato.'
            : 'Se crea como borrador: solo tú lo verás hasta que lo publiques.'
        }
      />
      <Card>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-5" noValidate>
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nombre</FormLabel>
                    <FormControl>
                      <Input autoComplete="off" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="location"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Lugar</FormLabel>
                    <FormControl>
                      <Input autoComplete="off" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid gap-5 sm:grid-cols-2">
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
                    {isEdit && current && current.registered_count > 0 && (
                      <FormDescription>
                        No puede ser menor que los {current.registered_count} inscritos actuales.
                      </FormDescription>
                    )}
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
                      <Textarea rows={5} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button type="button" variant="outline" onClick={() => navigate(-1)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting && <Spinner className="size-4 text-current" />}
                  {isEdit ? 'Guardar cambios' : 'Crear evento'}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
