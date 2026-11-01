import { Mic, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { speakersApi } from '@/api/speakers'
import type { Speaker } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { SpeakerFormDialog } from '@/features/speakers/SpeakerFormDialog'
import { useAsyncData } from '@/hooks/useAsyncData'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { usePageState } from '@/hooks/usePageState'
import { describeError } from '@/utils/errors'

const PAGE_SIZE = 10

export default function SpeakersPage() {
  const [text, setText] = useState('')
  const q = useDebouncedValue(text).trim()
  const [page, setPage] = usePageState(q)
  const {
    data,
    error,
    loading,
    reload: load,
  } = useAsyncData(
    () => speakersApi.list({ q: q || undefined, page, page_size: PAGE_SIZE }),
    [q, page],
  )
  const [editing, setEditing] = useState<Speaker | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Speaker | null>(null)

  async function remove(speaker: Speaker) {
    try {
      await speakersApi.remove(speaker.id)
      toast.success('Ponente eliminado')
      load()
    } catch (e) {
      toast.error(describeError(e))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ponentes"
        description="Personas que dictan las sesiones. No necesitan una cuenta de usuario."
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus /> Nuevo ponente
          </Button>
        }
      />

      <div className="grid max-w-sm gap-1.5">
        <Label htmlFor="speaker-search">Buscar por nombre</Label>
        <div className="relative">
          <Search
            className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            id="speaker-search"
            type="search"
            className="pl-9"
            value={text}
            onChange={(e) => setText(e.target.value)}
            autoComplete="off"
          />
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={load} />
      ) : loading && !data ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : !data || data.total === 0 ? (
        <EmptyState
          icon={<Mic />}
          title={q ? 'Sin resultados' : 'Aún no hay ponentes'}
          description={
            q ? 'Prueba con otro nombre.' : 'Crea el primero para asignarlo a una sesión.'
          }
        />
      ) : (
        <div className="space-y-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead className="hidden sm:table-cell">Correo</TableHead>
                <TableHead className="hidden md:table-cell">Biografía</TableHead>
                <TableHead className="w-24 text-right">
                  <span className="sr-only">Acciones</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((speaker) => (
                <TableRow key={speaker.id}>
                  <TableCell className="font-medium">{speaker.name}</TableCell>
                  <TableCell className="hidden sm:table-cell">{speaker.email ?? '—'}</TableCell>
                  <TableCell className="hidden max-w-xs truncate md:table-cell">
                    {speaker.bio ?? '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Editar ${speaker.name}`}
                      onClick={() => setEditing(speaker)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="text-destructive"
                      aria-label={`Eliminar ${speaker.name}`}
                      onClick={() => setDeleting(speaker)}
                    >
                      <Trash2 />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={data.page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onPageChange={setPage}
          />
        </div>
      )}

      {editing && (
        <SpeakerFormDialog
          speaker={editing === 'new' ? undefined : editing}
          open
          onOpenChange={(open) => !open && setEditing(null)}
          onSaved={load}
        />
      )}
      {deleting && (
        <ConfirmDialog
          open
          onOpenChange={(open) => !open && setDeleting(null)}
          title="Eliminar ponente"
          description={`Se eliminará a ${deleting.name}. No es posible si tiene sesiones asignadas.`}
          confirmLabel="Eliminar"
          destructive
          onConfirm={() => remove(deleting)}
        />
      )}
    </div>
  )
}
