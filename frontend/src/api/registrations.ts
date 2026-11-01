import { api } from '@/api/client'
import type { Attendee, MyRegistration, Page } from '@/api/types'

export const registrationsApi = {
  register: (eventId: string) => api.post(`/events/${eventId}/registrations`).then(() => undefined),
  cancel: (eventId: string) =>
    api.delete(`/events/${eventId}/registrations/me`).then(() => undefined),
  mine: () => api.get<MyRegistration[]>('/users/me/registrations').then((r) => r.data),
  attendees: (eventId: string, page = 1, pageSize = 20) =>
    api
      .get<Page<Attendee>>(`/events/${eventId}/registrations`, {
        params: { page, page_size: pageSize },
      })
      .then((r) => r.data),
}
