import { CalendarDays, MapPin } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { AppEvent } from '@/api/types'
import { StatusBadge } from '@/components/StatusBadge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AvailabilityBar } from '@/features/events/AvailabilityBar'
import { formatRange } from '@/utils/date'

export function EventCard({ event }: { event: AppEvent }) {
  return (
    <Card className="h-full gap-4 transition-shadow focus-within:ring-[3px] focus-within:ring-ring/50 hover:shadow-md">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <CardTitle asChild className="line-clamp-2 text-lg leading-snug">
            <h2>
              <Link
                to={`/events/${event.id}`}
                className="outline-none after:absolute after:inset-0"
              >
                {event.name}
              </Link>
            </h2>
          </CardTitle>
          <StatusBadge status={event.status} />
        </div>
      </CardHeader>
      <CardContent className="mt-auto space-y-3">
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <CalendarDays className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{formatRange(event.start_at, event.end_at)}</span>
        </p>
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span className="line-clamp-1">{event.location}</span>
        </p>
        <AvailabilityBar registered={event.registered_count} capacity={event.capacity} />
      </CardContent>
    </Card>
  )
}
