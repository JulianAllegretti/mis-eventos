import { useState } from 'react'

/** Número de página que vuelve a 1 cada vez que cambia `resetKey` (p. ej. el texto de búsqueda). */
export function usePageState(resetKey: string): [number, (page: number) => void] {
  const [state, setState] = useState({ key: resetKey, page: 1 })
  const page = state.key === resetKey ? state.page : 1
  return [page, (next) => setState({ key: resetKey, page: next })]
}
