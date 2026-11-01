import { api } from '@/api/client'
import type { Page, Speaker, SpeakerInput } from '@/api/types'

export const speakersApi = {
  list: (params: { q?: string; page?: number; page_size?: number }) =>
    api.get<Page<Speaker>>('/speakers', { params }).then((r) => r.data),
  create: (body: SpeakerInput) => api.post<Speaker>('/speakers', body).then((r) => r.data),
  update: (id: string, body: Partial<SpeakerInput>) =>
    api.patch<Speaker>(`/speakers/${id}`, body).then((r) => r.data),
  remove: (id: string) => api.delete(`/speakers/${id}`).then(() => undefined),
}
