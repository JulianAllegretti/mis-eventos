import { z } from 'zod'
import type { AppEvent, EventInput } from '@/api/types'
import { fromDatetimeLocal, toDatetimeLocal } from '@/utils/date'

export function makeEventSchema({ requireFutureStart }: { requireFutureStart: boolean }) {
  return z
    .object({
      name: z.string().trim().min(1, 'El nombre es obligatorio').max(200, 'Máximo 200 caracteres'),
      description: z.string().trim().max(5000, 'Máximo 5000 caracteres'),
      location: z
        .string()
        .trim()
        .min(1, 'El lugar es obligatorio')
        .max(200, 'Máximo 200 caracteres'),
      start_at: z.string().min(1, 'Indica cuándo empieza'),
      end_at: z.string().min(1, 'Indica cuándo termina'),
      capacity: z
        .number({ error: 'Indica la capacidad' })
        .int('Debe ser un número entero')
        .min(1, 'La capacidad mínima es 1')
        .max(100_000, 'La capacidad máxima es 100.000'),
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
      if (requireFutureStart && start <= Date.now()) {
        ctx.addIssue({
          code: 'custom',
          path: ['start_at'],
          message: 'El inicio debe estar en el futuro',
        })
      }
    })
}

export type EventFormValues = z.infer<ReturnType<typeof makeEventSchema>>

export const emptyEventForm: EventFormValues = {
  name: '',
  description: '',
  location: '',
  start_at: '',
  end_at: '',
  capacity: 50,
}

export function eventToFormValues(event: AppEvent): EventFormValues {
  return {
    name: event.name,
    description: event.description ?? '',
    location: event.location,
    start_at: toDatetimeLocal(event.start_at),
    end_at: toDatetimeLocal(event.end_at),
    capacity: event.capacity,
  }
}

export function formValuesToInput(values: EventFormValues): EventInput {
  return {
    name: values.name,
    description: values.description || null,
    location: values.location,
    start_at: fromDatetimeLocal(values.start_at),
    end_at: fromDatetimeLocal(values.end_at),
    capacity: values.capacity,
  }
}
