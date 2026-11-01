import { create } from 'zustand'
import { toApiError, type ApiError } from '@/api/client'
import { eventsApi, type ListEventsParams } from '@/api/events'
import type { AppEvent } from '@/api/types'

interface EventsState {
  items: AppEvent[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  error: ApiError | null

  current: AppEvent | null
  currentLoading: boolean
  currentError: ApiError | null

  fetchList: (params: ListEventsParams) => Promise<void>
  fetchEvent: (id: string) => Promise<AppEvent | null>
  setCurrent: (event: AppEvent) => void
  clearCurrent: () => void
}

// Solo vale la respuesta de la última petición: si el usuario escribe rápido, las anteriores
// se cancelan y nunca pisan el resultado más reciente.
let listController: AbortController | null = null
let currentController: AbortController | null = null

export const useEventsStore = create<EventsState>((set) => ({
  items: [],
  total: 0,
  page: 1,
  pageSize: 9,
  loading: false,
  error: null,

  current: null,
  currentLoading: false,
  currentError: null,

  fetchList: async (params) => {
    listController?.abort()
    const controller = new AbortController()
    listController = controller
    set({ loading: true, error: null })
    try {
      const result = await eventsApi.list(params, controller.signal)
      if (controller.signal.aborted) return
      set({
        items: result.items,
        total: result.total,
        page: result.page,
        pageSize: result.page_size,
        loading: false,
      })
    } catch (error) {
      const apiError = toApiError(error)
      if (apiError.code === 'cancelled' || controller.signal.aborted) return
      set({ error: apiError, loading: false })
    }
  },

  fetchEvent: async (id) => {
    currentController?.abort()
    const controller = new AbortController()
    currentController = controller
    set({ currentLoading: true, currentError: null })
    try {
      const event = await eventsApi.get(id, controller.signal)
      if (controller.signal.aborted) return null
      set({ current: event, currentLoading: false })
      return event
    } catch (error) {
      const apiError = toApiError(error)
      if (apiError.code === 'cancelled' || controller.signal.aborted) return null
      set({ currentError: apiError, currentLoading: false, current: null })
      return null
    }
  },

  setCurrent: (event) => set({ current: event }),
  clearCurrent: () => {
    currentController?.abort()
    set({ current: null, currentError: null, currentLoading: false })
  },
}))
