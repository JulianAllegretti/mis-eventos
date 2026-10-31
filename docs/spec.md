# Especificación funcional — Mis Eventos

Fuente: `docs/prd.pdf`. Este documento fija las reglas de negocio y resuelve los huecos del PRD. Las suposiciones están marcadas con **[S]** y deben confirmarse.

## 1. Alcance

**Obligatorio:** gestión de eventos con búsqueda, registro/login, sesiones con ponentes, gestión de asistentes, frontend completo, Docker, tests y documentación.
**Bonus incluidos:** roles y permisos, rendimiento frontend (lazy loading, WebP, minificación), caching con Redis, linting.

## 2. Actores y roles

| Rol | Descripción |
|---|---|
| `attendee` | Rol por defecto al registrarse. Ve eventos publicados, se inscribe y ve sus inscripciones. |
| `organizer` | Crea eventos y gestiona los propios (sesiones, ponentes, estado). |
| `admin` | Todo lo anterior sobre cualquier evento, más gestión de usuarios y roles. |

**[S]** El PRD dice que "usuarios autenticados" crean eventos; con el bonus de roles se restringe a `organizer` y `admin`. El primer admin se crea por variables de entorno (seed al arrancar). Solo un admin cambia roles.

## 3. Reglas de negocio

### 3.1 Usuarios y autenticación
- Registro con email único (normalizado a minúsculas) y contraseña (mínimo 8 caracteres, se valida longitud máxima de 128).
- Contraseña almacenada con argon2id; nunca se devuelve en respuestas.
- Login establece un JWT de acceso en una cookie `HttpOnly` con expiración configurable (por defecto 60 min); el token no se devuelve en el cuerpo. Logout borra la cookie y `GET /auth/me` devuelve la sesión actual. **[S]** Sin refresh token.
- Rutas de escritura y de perfil requieren token válido; la lectura de eventos publicados es pública.
- Mensajes de error de login genéricos (no revelan si el email existe).

### 3.2 Eventos
- Campos: nombre, descripción, ubicación, fecha/hora de inicio y fin, capacidad (entero ≥ 1), estado, organizador (creador).
- Estados **[S]**: `draft` → `published` → `finished`; `draft|published` → `cancelled`.
  - `draft`: visible solo para su organizador y admin.
  - `published`: visible para todos y admite inscripciones.
  - `cancelled` y `finished`: visibles, no admiten inscripciones ni cambios de datos.
  - Transiciones inversas no permitidas; el servidor responde 409.
  - **Cierre automático:** un evento `published` pasa a `finished` cuando su fecha fin ya pasó. Una tarea periódica lo persiste cada 60 s y, mientras tanto, la API lo trata como `finished` (ADR 0008). El organizador o un admin también puede finalizarlo antes de tiempo.
  - **Trazabilidad:** al finalizar o cancelar un evento se registra `closed_at`, `closed_by_id` (nulo si lo cerró el sistema) y `closed_source` (`manual` o `scheduler`), para poder distinguir cierres automáticos de manuales en estadísticas futuras.
- Validaciones: fin > inicio; inicio en el futuro al crear/publicar; capacidad no puede reducirse por debajo de los inscritos actuales.
- Edición y borrado: solo el organizador dueño o un admin. No se puede borrar un evento con inscripciones (se cancela).
- Búsqueda por nombre: coincidencia parcial sin distinguir mayúsculas, con parámetros ligados. Se escapan `%` y `_` del texto del usuario. Listado paginado (`page`, `page_size`, máximo 50), ordenado por fecha de inicio.

### 3.3 Ponentes
- **[S]** Entidad propia (no usuario): nombre, email opcional, bio. Gestionados por organizadores y admin; reutilizables entre eventos.

### 3.4 Sesiones
- Campos: título, descripción, evento, ponente, inicio, fin, capacidad.
- Validaciones de horario:
  - fin > inicio;
  - la sesión debe estar dentro del rango del evento;
  - un mismo ponente no puede tener dos sesiones solapadas (en cualquier evento);
  - **[S]** dos sesiones del mismo evento pueden solaparse solo si usan ponentes distintos (tracks paralelos).
- Capacidad de sesión ≤ capacidad del evento.
- **[S]** Un asistente inscrito en el evento puede inscribirse a sesiones; no se admiten más inscritos que la capacidad. No puede inscribirse a dos sesiones solapadas.

### 3.5 Inscripciones
- Un usuario autenticado se inscribe a un evento `published` si hay cupo.
- Una sola inscripción activa por usuario y evento (restricción única).
- El control de cupo es atómico: un filtro previo en Redis (contador con script Lua) rechaza rápido cuando no hay cupo, y PostgreSQL decide de forma definitiva con una actualización condicional y la restricción única. Con dos usuarios compitiendo por el último cupo, solo uno se inscribe y el otro recibe 409 (ver ADR 0005).
- **[S]** El usuario puede cancelar su inscripción (libera cupo y sus inscripciones a sesiones de ese evento).
- Perfil: lista de eventos en los que el usuario está inscrito.

### 3.6 Administración
- Admin lista usuarios, cambia rol y activa/desactiva cuentas (gestión de perfiles).

## 4. Requisitos no funcionales
- **Seguridad:** argon2id, consultas parametrizadas, CORS restringido por variable de entorno, secretos solo por entorno, validación de entrada con Pydantic.
- **Rendimiento y concurrencia:** Redis como filtro previo de cupos y caché de listado y detalle (TTL 60 s, invalidación en escritura); si Redis falla, la API sigue funcionando y PostgreSQL mantiene la corrección.
- **Observabilidad:** logs JSON con `request_id` (sin datos sensibles), `/health` y `/health/ready`, métricas Prometheus en `/metrics`, y un stack opcional Loki + Alloy + Prometheus + Grafana en el perfil de Compose `observability` (ADR 0009).
- **Documentación:** OpenAPI en `/docs`, READMEs de backend y frontend, documentación de estructura del frontend.
- **Calidad:** pytest con cobertura (objetivo ≥ 80 %), Vitest con cobertura, ruff y ESLint.
- **Entorno:** Docker Compose con backend, frontend, PostgreSQL y Redis; variables en `.env`.

## 5. Casos de error comunes
| Situación | Respuesta |
|---|---|
| Sin token / token inválido | 401 |
| Sin permiso por rol o propiedad | 403 |
| Recurso inexistente (o borrador ajeno) | 404 |
| Evento lleno, duplicado, transición inválida, solape de horario | 409 |
| Datos inválidos | 422 |

## 6. Decisiones confirmadas
1. Solo `organizer` y `admin` crean eventos; el primer admin sale de variables de entorno.
2. Los asistentes se inscriben a sesiones concretas, con control de cupo y sin solapes (3.4).
3. **No hay subida de imágenes.** Los eventos no tienen imagen propia; las imágenes son solo assets estáticos del diseño, optimizados en el frontend (WebP y `srcset`).
4. Los ponentes son una entidad propia y no necesitan usuario (3.3).

## 7. Preguntas abiertas
Ninguna por ahora. Las demás suposiciones **[S]** (estados del evento, cancelación de inscripción, sin refresh token) siguen vigentes hasta que se indique lo contrario.
