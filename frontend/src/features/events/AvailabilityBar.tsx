import { cn } from '@/lib/utils'

interface AvailabilityBarProps {
  registered: number
  capacity: number
  className?: string
}

/** Barra de ocupación con texto accesible: "12 de 40 cupos ocupados". */
export function AvailabilityBar({ registered, capacity, className }: AvailabilityBarProps) {
  const ratio = capacity > 0 ? Math.min(1, registered / capacity) : 0
  const full = registered >= capacity
  return (
    <div className={cn('space-y-1', className)}>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={capacity}
        aria-valuenow={registered}
        aria-label={`${registered} de ${capacity} cupos ocupados`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn(
            'h-full rounded-full transition-all',
            full ? 'bg-destructive' : 'bg-primary',
          )}
          style={{ width: `${ratio * 100}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        {full
          ? 'Sin cupos disponibles'
          : `${capacity - registered} de ${capacity} cupos disponibles`}
      </p>
    </div>
  )
}
