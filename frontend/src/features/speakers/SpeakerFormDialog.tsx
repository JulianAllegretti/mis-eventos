import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'
import { speakersApi } from '@/api/speakers'
import type { Speaker } from '@/api/types'
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
import { Textarea } from '@/components/ui/textarea'
import { describeError } from '@/utils/errors'

const speakerSchema = z.object({
  name: z.string().trim().min(1, 'El nombre es obligatorio').max(120, 'Máximo 120 caracteres'),
  email: z.union([z.literal(''), z.email('Correo inválido')]),
  bio: z.string().trim().max(2000, 'Máximo 2000 caracteres'),
})

type SpeakerFormValues = z.infer<typeof speakerSchema>

interface SpeakerFormDialogProps {
  speaker?: Speaker
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

export function SpeakerFormDialog({
  speaker,
  open,
  onOpenChange,
  onSaved,
}: SpeakerFormDialogProps) {
  const defaults: SpeakerFormValues = {
    name: speaker?.name ?? '',
    email: speaker?.email ?? '',
    bio: speaker?.bio ?? '',
  }
  const form = useForm<SpeakerFormValues>({
    resolver: zodResolver(speakerSchema),
    defaultValues: defaults,
  })

  useEffect(() => {
    if (open) form.reset(defaults)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, speaker?.id])

  async function onSubmit(values: SpeakerFormValues) {
    const body = { name: values.name, email: values.email || null, bio: values.bio || null }
    try {
      if (speaker) await speakersApi.update(speaker.id, body)
      else await speakersApi.create(body)
      toast.success(speaker ? 'Ponente actualizado' : 'Ponente creado')
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
          <DialogTitle>{speaker ? 'Editar ponente' : 'Nuevo ponente'}</DialogTitle>
          <DialogDescription>Un ponente no necesita una cuenta de usuario.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
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
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Correo (opcional)</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="bio"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Biografía (opcional)</FormLabel>
                  <FormControl>
                    <Textarea rows={4} {...field} />
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
                {speaker ? 'Guardar cambios' : 'Crear ponente'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
