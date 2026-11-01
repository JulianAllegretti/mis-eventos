import { api } from '@/api/client'
import type { Page, Role, User } from '@/api/types'

export const adminApi = {
  listUsers: (params: { q?: string; page?: number; page_size?: number }) =>
    api.get<Page<User>>('/admin/users', { params }).then((r) => r.data),
  updateUser: (id: string, body: { role?: Role; is_active?: boolean }) =>
    api.patch<User>(`/admin/users/${id}`, body).then((r) => r.data),
}
