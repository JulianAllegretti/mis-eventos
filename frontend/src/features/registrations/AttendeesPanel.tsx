import { Users } from 'lucide-react'
import { useState } from 'react'
import { registrationsApi } from '@/api/registrations'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { Spinner } from '@/components/Spinner'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAsyncData } from '@/hooks/useAsyncData'
import { formatDateTime } from '@/utils/date'

const PAGE_SIZE = 10

/** Lista de asistentes inscritos. Solo la ven el organizador del evento y los administradores. */
export function AttendeesPanel({ eventId }: { eventId: string }) {
  const [page, setPage] = useState(1)
  const { data, error, loading, reload } = useAsyncData(
    () => registrationsApi.attendees(eventId, page, PAGE_SIZE),
    [eventId, page],
  )

  if (error) return <ErrorState error={error} onRetry={reload} />
  if (loading && !data) return <Spinner />
  if (!data || data.total === 0) {
    return <EmptyState icon={<Users />} title="Todavía no hay inscritos" />
  }

  return (
    <div className="space-y-3" aria-busy={loading}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nombre</TableHead>
            <TableHead>Correo</TableHead>
            <TableHead>Inscrito el</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((a) => (
            <TableRow key={a.registration_id}>
              <TableCell className="font-medium">{a.full_name}</TableCell>
              <TableCell>{a.email}</TableCell>
              <TableCell>{formatDateTime(a.registered_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Pagination page={data.page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
    </div>
  )
}
