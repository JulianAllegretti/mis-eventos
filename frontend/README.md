# Frontend — Mis Eventos

Aplicación de una sola página con **React 19 + TypeScript + Vite**, **React Router**, **Zustand**, **Axios**, **Tailwind CSS 4** y **shadcn/ui**. Consume la API REST del backend (`../backend`).

## Puesta en marcha

### Con Docker (recomendado)

Desde la raíz del repositorio:

```bash
cp .env.example .env        # edita JWT_SECRET, POSTGRES_PASSWORD y ADMIN_PASSWORD
docker compose up --build   # db + redis + backend + frontend
```

- Aplicación: http://localhost:8080 (nginx sirve el frontend y reenvía `/api` al backend)
- Swagger de la API: http://localhost:8000/docs
- El primer administrador sale de `ADMIN_EMAIL` / `ADMIN_PASSWORD` del `.env`.

### En desarrollo (sin Docker para el frontend)

Requiere Node 24+ y el backend corriendo en `http://localhost:8000`.

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173 (proxy de /api → localhost:8000)
```

Si el backend corre en otra dirección: `VITE_API_PROXY=http://host:puerto npm run dev`.
Para que el backend acepte las peticiones con cookie desde ese origen, `ALLOWED_ORIGINS` debe incluir `http://localhost:5173` (ya viene así en `.env.example`).

## Scripts

| Comando                           | Qué hace                                       |
| --------------------------------- | ---------------------------------------------- |
| `npm run dev`                     | Servidor de desarrollo con recarga en caliente |
| `npm run build`                   | Comprueba tipos y genera `dist/` minificado    |
| `npm test`                        | Pruebas unitarias y de integración (Vitest)    |
| `npm run coverage`                | Pruebas con reporte de cobertura (`coverage/`) |
| `npm run lint`                    | ESLint                                         |
| `npm run typecheck`               | TypeScript sin emitir                          |
| `npm run format` / `format:check` | Prettier                                       |

## Estructura

```
src/
├── main.tsx                 # punto de entrada: tema claro/oscuro y router
├── api/                     # cliente HTTP y un módulo por recurso
│   ├── client.ts            #   Axios (withCredentials), errores normalizados (ApiError), manejo de 401
│   ├── types.ts             #   tipos de la API
│   └── auth|events|sessions|registrations|speakers|admin.ts
├── stores/                  # estado global (Zustand)
│   ├── authStore.ts         #   usuario y estado de la sesión (no guarda el token)
│   ├── eventsStore.ts       #   lista, evento actual, paginación; descarta respuestas obsoletas
│   └── registrationsStore.ts#   mis inscripciones (eventos y sesiones)
├── routes/                  # tabla de rutas (carga diferida), guardas y layout
├── pages/                   # una página por ruta
├── features/                # piezas de dominio: events, sessions, speakers, registrations
├── components/              # reutilizables: Navbar, Pagination, ConfirmDialog, StatusBadge…
│   └── ui/                  #   primitivas de shadcn/ui (button, input, dialog, select, table…)
├── hooks/                   # useAsyncData, useDebouncedValue, usePageState
├── utils/                   # fechas (es-CO) y mensajes de error
├── styles/globals.css       # tema (variables CSS), Tailwind
└── test/                    # configuración de pruebas, MSW, fábricas y helpers de render
```

### Rutas

| Ruta                  | Página                                    | Acceso               |
| --------------------- | ----------------------------------------- | -------------------- |
| `/`                   | Listado con búsqueda, filtro y paginación | Público              |
| `/events/:id`         | Detalle, agenda e inscripción             | Público              |
| `/events/new`         | Crear evento                              | `organizer`, `admin` |
| `/events/:id/edit`    | Editar evento                             | `organizer`, `admin` |
| `/speakers`           | Gestión de ponentes                       | `organizer`, `admin` |
| `/admin/users`        | Roles y activación de cuentas             | `admin`              |
| `/profile`            | Mi perfil y mis inscripciones             | Autenticado          |
| `/login`, `/register` | Autenticación                             | Solo sin sesión      |

La búsqueda, el filtro y la página del listado viven en la URL (`/?q=python&status=published&page=2`), así que se pueden compartir y funcionan con el botón «atrás».

### Estado

- **`authStore`**: `user` y `status` (`unknown | authenticated | anonymous`). La sesión es una **cookie HttpOnly** que JavaScript no puede leer; al abrir la app se restaura con `GET /auth/me`. Un 401 en cualquier otra ruta cierra la sesión local.
- **`eventsStore`**: lista (`items`, `total`, `page`), evento actual y errores. Cada petición nueva cancela la anterior (`AbortController`), de modo que escribir rápido en el buscador nunca muestra resultados viejos.
- **`registrationsStore`**: inscripciones del usuario; se recarga tras cada cambio.

### Componentes reutilizables

`EventCard`, `AvailabilityBar`, `StatusBadge`, `Pagination`, `ConfirmDialog`, `EmptyState`, `ErrorState`, `PageHeader`, `Spinner`, `SessionList`, `SessionFormDialog`, `SpeakerFormDialog`, `AttendeesPanel`, `EventActions` y las primitivas de `components/ui/`. Los formularios usan **react-hook-form + zod** y los avisos **sonner**.

## Interfaz y rendimiento

- **Responsiva** (mobile-first con los breakpoints de Tailwind): rejilla de 1/2/3 columnas, navegación que se pliega en un menú, tablas con scroll horizontal. Sin scroll horizontal a 390 px.
- **Estados de carga y error**: esqueletos, spinners, botones deshabilitados al enviar, avisos de éxito/error y reintento.
- **Accesible**: encabezados reales, etiquetas en todos los campos, foco visible, enlace «Saltar al contenido», `aria-live` en los contadores y respeto de `prefers-reduced-motion`.
- **Carga diferida** de cada ruta (`React.lazy`) y separación de librerías pesadas en paquetes aparte; el HTML no se cachea y los archivos con hash sí (1 año, `immutable`).
- **Imágenes WebP** con `srcset` en tres anchos (640/1280/1920 px). Los eventos no tienen imagen propia: solo hay imágenes de diseño.
- **Minificación** de producción con Vite; nginx comprime con gzip.

## Seguridad

- Cookie de sesión `HttpOnly` + `SameSite=Lax`; el frontend nunca maneja el token ni usa `localStorage`.
- Frontend y API comparten origen a través de nginx (sin CORS); el navegador envía `Origin` y el backend rechaza las escrituras con cookie desde orígenes no permitidos.
- nginx envía una **CSP** estricta (`default-src 'self'`, sin scripts en línea), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` y `Permissions-Policy`, y corre como usuario sin privilegios.
- No se usa `dangerouslySetInnerHTML`: todo el texto se escapa.

## Pruebas

```bash
npm test            # 150+ pruebas
npm run coverage    # reporte en coverage/index.html
```

- **Vitest + Testing Library** para componentes y páginas; **MSW** simula la API de red real (los flujos pasan por Axios, interceptores y stores reales).
- Se prueban: validaciones de formularios, inscripción (incluido evento lleno y choques de horario), agenda, acciones del organizador, administración, guardas de rutas por rol, paginación y búsqueda con debounce, cancelación de peticiones obsoletas, normalización de errores y cierre de sesión.
- `src/test/setup.ts` incluye los polyfills de jsdom que necesita Radix UI (`ResizeObserver`, `matchMedia`, captura de puntero).

## Decisiones y notas

- **TypeScript 6.0.x**: la versión 7 aún no es compatible con `typescript-eslint` (que exige `<6.1`); se fija la serie 6.0 para conservar el linter.
- **shadcn/ui**: los componentes de `components/ui/` están en el repositorio (a la manera de la CLI de shadcn, con Tailwind 4 y Radix) y se pueden modificar.
- **Sin estado de servidor en caché**: se prefirió Zustand + hooks pequeños (`useAsyncData`) a una librería de consultas para mantener pocas dependencias; la caché de lectura vive en el backend (Redis).
