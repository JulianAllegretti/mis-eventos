import type { EventStatus } from '@/api/types'
import { Badge } from '@/components/ui/badge'

const CONFIG: Record<
  EventStatus,
  { label: string; variant: 'muted' | 'success' | 'secondary' | 'destructive' }
> = {
  draft: { label: 'Borrador', variant: 'muted' },
  published: { label: 'Publicado', variant: 'success' },
  finished: { label: 'Finalizado', variant: 'secondary' },
  cancelled: { label: 'Cancelado', variant: 'destructive' },
}

export function StatusBadge({ status }: { status: EventStatus }) {
  const { label, variant } = CONFIG[status]
  return <Badge variant={variant}>{label}</Badge>
}
