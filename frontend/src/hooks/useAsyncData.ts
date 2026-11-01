import { useCallback, useEffect, useRef, useState } from 'react'

interface State<T> {
  key: string
  data: T | null
  error: unknown
}

/**
 * Carga datos asíncronos que dependen de `deps`.
 *
 * El estado de carga se deriva comparando la clave de la última respuesta con la clave actual
 * (dependencias + recargas), así no hace falta llamar a `setState` dentro del efecto. Mientras
 * llega la respuesta nueva se conservan los datos anteriores (`data`) para evitar parpadeos, y las
 * respuestas de peticiones obsoletas se descartan.
 */
export function useAsyncData<T>(fetcher: () => Promise<T>, deps: readonly unknown[]) {
  const [reloads, setReloads] = useState(0)
  const [state, setState] = useState<State<T>>({ key: '', data: null, error: null })
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  const key = `${JSON.stringify(deps)}#${reloads}`

  useEffect(() => {
    let cancelled = false
    fetcherRef.current().then(
      (data) => {
        if (!cancelled) setState({ key, data, error: null })
      },
      (error: unknown) => {
        if (!cancelled) setState((prev) => ({ key, data: prev.data, error }))
      },
    )
    return () => {
      cancelled = true
    }
  }, [key])

  const reload = useCallback(() => setReloads((n) => n + 1), [])
  /** Actualiza localmente los datos ya cargados (p. ej. tras editar una fila). */
  const mutate = useCallback(
    (update: (data: T) => T) =>
      setState((prev) => (prev.data === null ? prev : { ...prev, data: update(prev.data) })),
    [],
  )

  return {
    data: state.data,
    error: state.key === key ? state.error : null,
    loading: state.key !== key,
    reload,
    mutate,
  }
}
