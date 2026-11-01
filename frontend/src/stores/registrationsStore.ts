import { create } from 'zustand'
import { registrationsApi } from '@/api/registrations'
import type { MyRegistration } from '@/api/types'

interface RegistrationsState {
  items: MyRegistration[]
  loaded: boolean
  loading: boolean
  load: () => Promise<void>
  reset: () => void
  isRegisteredToEvent: (eventId: string) => boolean
  isRegisteredToSession: (sessionId: string) => boolean
}

/** Inscripciones del usuario actual (eventos y sesiones). Se recarga tras cada cambio. */
export const useRegistrationsStore = create<RegistrationsState>((set, get) => ({
  items: [],
  loaded: false,
  loading: false,
  load: async () => {
    set({ loading: true })
    try {
      set({ items: await registrationsApi.mine(), loaded: true })
    } finally {
      set({ loading: false })
    }
  },
  reset: () => set({ items: [], loaded: false, loading: false }),
  isRegisteredToEvent: (eventId) => get().items.some((r) => r.event.id === eventId),
  isRegisteredToSession: (sessionId) =>
    get().items.some((r) => r.sessions.some((s) => s.id === sessionId)),
}))
