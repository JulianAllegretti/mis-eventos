import { api } from '@/api/client'
import type { AppEvent, EventInput, EventStatus, Page } from '@/api/types'

export interface ListEventsParams {
  q?: string
  status?: EventStatus
  scope?: 'all' | 'mine'
  page?: number
  page_size?: number
}

export const eventsApi = {
  list: (params: ListEventsParams, signal?: AbortSignal) =>
    api.get<Page<AppEvent>>('/events', { params, signal }).then((r) => r.data),
  get: (id: string, signal?: AbortSignal) =>
    api.get<AppEvent>(`/events/${id}`, { signal }).then((r) => r.data),
  create: (body: EventInput) => api.post<AppEvent>('/events', body).then((r) => r.data),
  update: (id: string, body: Partial<EventInput>) =>
    api.patch<AppEvent>(`/events/${id}`, body).then((r) => r.data),
  remove: (id: string) => api.delete(`/events/${id}`).then(() => undefined),
  publish: (id: string) => api.post<AppEvent>(`/events/${id}/publish`).then((r) => r.data),
  finish: (id: string) => api.post<AppEvent>(`/events/${id}/finish`).then((r) => r.data),
  cancel: (id: string) => api.post<AppEvent>(`/events/${id}/cancel`).then((r) => r.data),
}
