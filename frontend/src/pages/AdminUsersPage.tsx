import { Search, Users } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { adminApi } from '@/api/admin'
import type { Role, User } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { PageHeader } from '@/components/PageHeader'
import { Pagination } from '@/components/Pagination'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAsyncData } from '@/hooks/useAsyncData'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { usePageState } from '@/hooks/usePageState'
import { useAuthStore } from '@/stores/authStore'
import { describeError } from '@/utils/errors'

const PAGE_SIZE = 10
const ROLES: { value: Role; label: string }[] = [
  { value: 'attendee', label: 'Asistente' },
  { value: 'organizer', label: 'Organizador' },
  { value: 'admin', label: 'Administrador' },
]

export default function AdminUsersPage() {
  const me = useAuthStore((s) => s.user)
  const [text, setText] = useState('')
  const q = useDebouncedValue(text).trim()
  const [page, setPage] = usePageState(q)
  const {
    data,
    error,
    loading,
    reload: load,
    mutate,
  } = useAsyncData(
    () => adminApi.listUsers({ q: q || undefined, page, page_size: PAGE_SIZE }),
    [q, page],
  )
  const [savingId, setSavingId] = useState<string | null>(null)

  async function update(user: User, changes: { role?: Role; is_active?: boolean }) {
    setSavingId(user.id)
    try {
      const updated = await adminApi.updateUser(user.id, changes)
      mutate((current) => ({
        ...current,
        items: current.items.map((u) => (u.id === updated.id ? updated : u)),
      }))
      toast.success('Usuario actualizado')
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Usuarios"
        description="Cambia roles y activa o desactiva cuentas. Los cambios aplican de inmediato."
      />

      <div className="grid max-w-sm gap-1.5">
        <Label htmlFor="user-search">Buscar por correo o nombre</Label>
        <div className="relative">
          <Search
            className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            id="user-search"
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
          icon={<Users />}
          title="Sin resultados"
          description="Prueba con otro correo o nombre."
        />
      ) : (
        <div className="space-y-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Usuario</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Activo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((user) => {
                const isMe = user.id === me?.id
                const disabled = isMe || savingId === user.id
                return (
                  <TableRow key={user.id}>
                    <TableCell>
                      <p className="font-medium">
                        {user.full_name}{' '}
                        {isMe && <span className="text-xs text-muted-foreground">(tú)</span>}
                      </p>
                      <p className="text-xs text-muted-foreground">{user.email}</p>
                    </TableCell>
                    <TableCell>
                      <Select
                        value={user.role}
                        disabled={disabled}
                        onValueChange={(role) => void update(user, { role: role as Role })}
                      >
                        <SelectTrigger
                          size="sm"
                          aria-label={`Rol de ${user.full_name}`}
                          className="w-40"
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((r) => (
                            <SelectItem key={r.value} value={r.value}>
                              {r.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Switch
                        checked={user.is_active}
                        disabled={disabled}
                        aria-label={`Cuenta activa de ${user.full_name}`}
                        onCheckedChange={(checked) => void update(user, { is_active: checked })}
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
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
    </div>
  )
}
