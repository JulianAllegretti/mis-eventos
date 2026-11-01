import { CalendarX2, Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { EventStatus } from '@/api/types'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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
import { EventCard } from '@/features/events/EventCard'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { selectIsManager, useAuthStore } from '@/stores/authStore'
import { useEventsStore } from '@/stores/eventsStore'

const PAGE_SIZE = 9
type StatusFilter = 'all' | Extract<EventStatus, 'published' | 'finished'>

function parsePage(value: string | null) {
  const n = Number(value)
  return Number.isInteger(n) && n >= 1 ? n : 1
}

export default function EventListPage() {
  const [params, setParams] = useSearchParams()
  const user = useAuthStore((s) => s.user)
  const { items, total, page, loading, error, fetchList } = useEventsStore()

  const q = params.get('q') ?? ''
  const pageParam = parsePage(params.get('page'))
  const status = (params.get('status') as StatusFilter | null) ?? 'all'
  const mine = params.get('scope') === 'mine' && selectIsManager(user)

  const [text, setText] = useState(q)
  const debouncedText = useDebouncedValue(text)

  function updateParams(changes: Record<string, string | null>) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === '' || value === 'all') next.delete(key)
          else next.set(key, value)
        }
        return next
      },
      { replace: true },
    )
  }

  // La búsqueda se aplica al dejar de escribir y siempre vuelve a la primera página.
  useEffect(() => {
    if (debouncedText.trim() !== q) updateParams({ q: debouncedText.trim(), page: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedText])

  useEffect(() => {
    void fetchList({
      q: q || undefined,
      status: status === 'all' ? undefined : status,
      scope: mine ? 'mine' : undefined,
      page: pageParam,
      page_size: PAGE_SIZE,
    })
  }, [q, status, mine, pageParam, fetchList])

  const hasFilters = Boolean(q) || status !== 'all' || mine

  return (
    <div className="space-y-8">
      <section className="relative isolate overflow-hidden rounded-2xl bg-primary text-primary-foreground">
        <picture>
          <source
            type="image/webp"
            srcSet="/images/hero-640.webp 640w, /images/hero-1280.webp 1280w, /images/hero-1920.webp 1920w"
            sizes="(min-width: 1152px) 1152px, 100vw"
          />
          <img
            src="/images/hero-1280.webp"
            alt=""
            width={1280}
            height={480}
            decoding="async"
            fetchPriority="high"
            className="absolute inset-0 -z-10 size-full object-cover opacity-70"
          />
        </picture>
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-primary/90 via-primary/60 to-transparent" />
        <div className="space-y-4 px-6 py-12 sm:px-10 sm:py-16">
          <h1 className="max-w-xl text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            Descubre eventos y asegura tu lugar
          </h1>
          <p className="max-w-lg text-primary-foreground/90">
            Conferencias, talleres y encuentros. Revisa la agenda, elige tus sesiones e inscríbete
            en segundos.
          </p>
          {selectIsManager(user) && (
            <Button variant="secondary" asChild>
              <Link to="/events/new">
                <Plus /> Crear evento
              </Link>
            </Button>
          )}
        </div>
      </section>

      <section aria-label="Filtros" className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="grid flex-1 gap-1.5">
          <Label htmlFor="search">Buscar por nombre</Label>
          <div className="relative">
            <Search
              className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="search"
              type="search"
              placeholder="Ej. Congreso de Python"
              className="pl-9"
              value={text}
              onChange={(e) => setText(e.target.value)}
              autoComplete="off"
            />
          </div>
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="status">Estado</Label>
          <Select
            value={status}
            onValueChange={(value) => updateParams({ status: value, page: null })}
          >
            <SelectTrigger id="status" className="w-full sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="published">Próximos</SelectItem>
              <SelectItem value="finished">Finalizados</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {selectIsManager(user) && (
          <div className="flex items-center gap-2 pb-2">
            <Switch
              id="mine"
              checked={mine}
              onCheckedChange={(checked) =>
                updateParams({ scope: checked ? 'mine' : null, page: null })
              }
            />
            <Label htmlFor="mine">Solo mis eventos</Label>
          </div>
        )}
      </section>

      <section aria-label="Resultados" aria-busy={loading} className="space-y-4">
        {error ? (
          <ErrorState
            error={error}
            onRetry={() =>
              void fetchList({ q: q || undefined, page: pageParam, page_size: PAGE_SIZE })
            }
          />
        ) : loading && items.length === 0 ? (
          <EventGridSkeleton />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<CalendarX2 />}
            title={hasFilters ? 'Sin resultados' : 'Aún no hay eventos publicados'}
            description={
              hasFilters
                ? 'Prueba con otro nombre o quita los filtros.'
                : 'Vuelve pronto: los organizadores están preparando nuevos eventos.'
            }
            action={
              hasFilters ? (
                <Button
                  variant="outline"
                  onClick={() => {
                    setText('')
                    setParams({}, { replace: true })
                  }}
                >
                  Limpiar filtros
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {total} {total === 1 ? 'evento' : 'eventos'}
            </p>
            <ul
              className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-3 ${loading ? 'opacity-60' : ''}`}
            >
              {items.map((event) => (
                <li key={event.id} className="relative">
                  <EventCard event={event} />
                </li>
              ))}
            </ul>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onPageChange={(next) => {
                updateParams({ page: String(next) })
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
            />
          </>
        )}
      </section>
    </div>
  )
}

function EventGridSkeleton() {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Cargando eventos">
      {Array.from({ length: 6 }, (_, i) => (
        <li key={i}>
          <Card className="gap-4">
            <CardHeader>
              <Skeleton className="h-5 w-3/4" />
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-2 w-full" />
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  )
}
