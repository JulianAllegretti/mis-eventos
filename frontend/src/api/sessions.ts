import { api } from '@/api/client'
import type { AgendaSession, SessionInput } from '@/api/types'

export const sessionsApi = {
  listForEvent: (eventId: string) =>
    api.get<AgendaSession[]>(`/events/${eventId}/sessions`).then((r) => r.data),
  create: (eventId: string, body: SessionInput) =>
    api.post<AgendaSession>(`/events/${eventId}/sessions`, body).then((r) => r.data),
  update: (id: string, body: Partial<SessionInput>) =>
    api.patch<AgendaSession>(`/sessions/${id}`, body).then((r) => r.data),
  remove: (id: string) => api.delete(`/sessions/${id}`).then(() => undefined),
  register: (id: string) => api.post(`/sessions/${id}/registrations`).then(() => undefined),
  cancelRegistration: (id: string) =>
    api.delete(`/sessions/${id}/registrations/me`).then(() => undefined),
}
