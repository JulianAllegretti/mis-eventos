import { z } from 'zod'
import type { AgendaSession, SessionInput } from '@/api/types'
import { fromDatetimeLocal, toDatetimeLocal } from '@/utils/date'

interface EventBounds {
  start_at: string
  end_at: string
  capacity: number
}

export function makeSessionSchema(event: EventBounds) {
  const eventStart = new Date(event.start_at).getTime()
  const eventEnd = new Date(event.end_at).getTime()
  return z
    .object({
      speaker_id: z.string().min(1, 'Elige un ponente'),
      title: z.string().trim().min(1, 'El título es obligatorio').max(200, 'Máximo 200 caracteres'),
      description: z.string().trim().max(2000, 'Máximo 2000 caracteres'),
      start_at: z.string().min(1, 'Indica cuándo empieza'),
      end_at: z.string().min(1, 'Indica cuándo termina'),
      capacity: z
        .number({ error: 'Indica la capacidad' })
        .int('Debe ser un número entero')
        .min(1, 'La capacidad mínima es 1')
        .max(event.capacity, `No puede superar la capacidad del evento (${event.capacity})`),
    })
    .superRefine((data, ctx) => {
      const start = new Date(data.start_at).getTime()
      const end = new Date(data.end_at).getTime()
      if (Number.isNaN(start) || Number.isNaN(end)) return
      if (end <= start) {
        ctx.addIssue({
          code: 'custom',
          path: ['end_at'],
          message: 'El fin debe ser posterior al inicio',
        })
      }
      if (start < eventStart || end > eventEnd) {
        ctx.addIssue({
          code: 'custom',
          path: ['start_at'],
          message: 'La sesión debe estar dentro del horario del evento',
        })
      }
    })
}

export type SessionFormValues = z.infer<ReturnType<typeof makeSessionSchema>>

export function sessionToFormValues(session: AgendaSession): SessionFormValues {
  return {
    speaker_id: session.speaker?.id ?? '',
    title: session.title,
    description: session.description ?? '',
    start_at: toDatetimeLocal(session.start_at),
    end_at: toDatetimeLocal(session.end_at),
    capacity: session.capacity,
  }
}

export function sessionValuesToInput(values: SessionFormValues): SessionInput {
  return {
    speaker_id: values.speaker_id,
    title: values.title,
    description: values.description || null,
    start_at: fromDatetimeLocal(values.start_at),
    end_at: fromDatetimeLocal(values.end_at),
    capacity: values.capacity,
  }
}
