import { CalendarDays, LogOut, Menu, User as UserIcon } from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { selectIsManager, useAuthStore } from '@/stores/authStore'

interface NavItem {
  to: string
  label: string
}

function useNavItems(): NavItem[] {
  const user = useAuthStore((s) => s.user)
  const items: NavItem[] = [{ to: '/', label: 'Eventos' }]
  if (selectIsManager(user)) {
    items.push({ to: '/events/new', label: 'Crear evento' }, { to: '/speakers', label: 'Ponentes' })
  }
  if (user?.role === 'admin') items.push({ to: '/admin/users', label: 'Usuarios' })
  return items
}

const ROLE_LABEL = {
  attendee: 'Asistente',
  organizer: 'Organizador',
  admin: 'Administrador',
} as const

export function Navbar() {
  const user = useAuthStore((s) => s.user)
  const status = useAuthStore((s) => s.status)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const items = useNavItems()

  async function handleLogout() {
    try {
      await logout()
      toast.success('Sesión cerrada')
    } finally {
      navigate('/')
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 font-semibold whitespace-nowrap">
            <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
              <CalendarDays className="size-4" aria-hidden />
            </span>
            Mis Eventos
          </Link>
          <nav aria-label="Principal" className="hidden items-center gap-1 md:flex">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground',
                    isActive && 'bg-accent text-accent-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          {status === 'authenticated' && user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" aria-label="Menú de usuario">
                  <UserIcon />
                  <span className="hidden max-w-32 truncate sm:inline">{user.full_name}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <p className="truncate">{user.full_name}</p>
                  <p className="truncate text-xs font-normal text-muted-foreground">
                    {ROLE_LABEL[user.role]}
                  </p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => navigate('/profile')}>
                  <UserIcon /> Mi perfil
                </DropdownMenuItem>
                <DropdownMenuItem variant="destructive" onSelect={handleLogout}>
                  <LogOut /> Cerrar sesión
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : status === 'anonymous' ? (
            <>
              {/* En pantallas muy angostas estas acciones viven en el menú desplegable. */}
              <Button variant="ghost" size="sm" className="hidden sm:inline-flex" asChild>
                <Link to="/login">Ingresar</Link>
              </Button>
              <Button size="sm" className="hidden sm:inline-flex" asChild>
                <Link to="/register">Crear cuenta</Link>
              </Button>
            </>
          ) : null}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="md:hidden"
                aria-label="Abrir navegación"
              >
                <Menu />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 md:hidden">
              {items.map((item) => (
                <DropdownMenuItem key={item.to} onSelect={() => navigate(item.to)}>
                  {item.label}
                </DropdownMenuItem>
              ))}
              {status === 'anonymous' && (
                <>
                  <DropdownMenuSeparator className="sm:hidden" />
                  <DropdownMenuItem className="sm:hidden" onSelect={() => navigate('/login')}>
                    Ingresar
                  </DropdownMenuItem>
                  <DropdownMenuItem className="sm:hidden" onSelect={() => navigate('/register')}>
                    Crear cuenta
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
