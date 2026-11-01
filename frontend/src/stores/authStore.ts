import { create } from 'zustand'
import { authApi } from '@/api/auth'
import { setUnauthorizedHandler } from '@/api/client'
import type { User } from '@/api/types'
import { useRegistrationsStore } from '@/stores/registrationsStore'

type AuthStatus = 'unknown' | 'authenticated' | 'anonymous'

interface AuthState {
  user: User | null
  /** `unknown` mientras se comprueba si hay sesión al abrir la app. */
  status: AuthStatus
  loadSession: () => Promise<void>
  login: (email: string, password: string) => Promise<User>
  register: (input: { email: string; password: string; full_name: string }) => Promise<User>
  logout: () => Promise<void>
  clearSession: () => void
}

/**
 * Estado de autenticación. No guarda el token: vive en una cookie HttpOnly que JavaScript no
 * puede leer; la sesión se restaura preguntando al backend (`GET /auth/me`).
 */
export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  status: 'unknown',

  loadSession: async () => {
    try {
      set({ user: await authApi.me(), status: 'authenticated' })
    } catch {
      set({ user: null, status: 'anonymous' })
    }
  },

  login: async (email, password) => {
    const user = await authApi.login({ email, password })
    set({ user, status: 'authenticated' })
    return user
  },

  register: async (input) => {
    await authApi.register(input)
    return get().login(input.email, input.password)
  },

  logout: async () => {
    try {
      await authApi.logout()
    } finally {
      get().clearSession()
    }
  },

  clearSession: () => {
    useRegistrationsStore.getState().reset()
    set({ user: null, status: 'anonymous' })
  },
}))

// Una respuesta 401 en cualquier otra ruta significa que la sesión caducó.
setUnauthorizedHandler(() => {
  if (useAuthStore.getState().status === 'authenticated') useAuthStore.getState().clearSession()
})

export const selectIsManager = (user: User | null) =>
  user?.role === 'organizer' || user?.role === 'admin'
