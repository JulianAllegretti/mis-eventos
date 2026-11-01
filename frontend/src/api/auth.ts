import { api } from '@/api/client'
import type { User } from '@/api/types'

export const authApi = {
  register: (body: { email: string; password: string; full_name: string }) =>
    api.post<User>('/auth/register', body).then((r) => r.data),
  login: (body: { email: string; password: string }) =>
    api.post<User>('/auth/login', body).then((r) => r.data),
  logout: () => api.post('/auth/logout').then(() => undefined),
  me: () => api.get<User>('/auth/me').then((r) => r.data),
}
