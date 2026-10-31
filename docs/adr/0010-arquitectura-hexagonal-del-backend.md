# ADR 0010: Arquitectura hexagonal (puertos y adaptadores) en el backend

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
El backend combina reglas de negocio no triviales (estados, cupos, solape de horarios, permisos) con varias dependencias externas (PostgreSQL, Redis, argon2, JWT, reloj, métricas). Si FastAPI y SQLModel se mezclan con la lógica, los tests unitarios requieren base de datos, y cambiar un componente (por ejemplo el filtro de cupos en Redis) afecta a todo el código.

## Decisión
Organizar `backend/app/` en capas con **puertos y adaptadores**, separando lo que entra al sistema (inbound) de lo que el sistema usa (outbound):

```
app/
├── domain/          # entidades, value objects, reglas puras, errores de dominio
├── application/     # casos de uso, puertos inbound y outbound, comandos/queries
├── adapters/
│   ├── inbound/     # http (routers, schemas, mappers, dependencias), jobs
│   └── outbound/    # persistence, security, cache, system, observability
└── bootstrap/       # composition root: configuración y cableado de dependencias
```

Reglas de dependencia (se verifican en CI con `import-linter`):
1. `domain` no importa nada del proyecto ni de frameworks (ni FastAPI, SQLModel, Redis, Pydantic).
2. `application` solo importa `domain`.
3. `adapters` importan `application` y `domain`; los adaptadores inbound y outbound **no se importan entre sí**.
4. Solo `bootstrap` conoce todos los adaptadores y los inyecta en los casos de uso.

Elementos:
- **Puertos inbound:** interfaces (`Protocol`) de los casos de uso que ofrece la aplicación, p. ej. `RegisterToEvent`. Los routers dependen de ellas.
- **Puertos outbound:** interfaces de lo que la aplicación necesita, p. ej. `EventRepository`, `UnitOfWork`, `SlotCounter`, `Cache`, `PasswordHasher`, `TokenService`, `Clock`, `Metrics`.
- **Adaptadores inbound:** HTTP (FastAPI) y la tarea periódica de cierre de eventos (ADR 0008).
- **Adaptadores outbound:** persistencia (SQLModel/SQLAlchemy), seguridad (argon2, JWT), caché y contador (Redis), reloj y métricas.
- **Mappers** en cada frontera, para que ningún modelo atraviese una capa que no le corresponde:
  - HTTP: `schema ↔ command/query` y `entidad/read model → schema de respuesta`.
  - Persistencia: `modelo SQLModel ↔ entidad de dominio`.
- Los modelos `SQLModel` (tablas) y los esquemas de Pydantic de la API viven **solo** en sus adaptadores; el dominio usa `dataclasses`.
- La transacción la gestiona el puerto `UnitOfWork`, que los casos de uso usan como contexto (`async with uow:`).

## Alternativas
- **Capas clásicas (routers → services → repositories con modelos SQLModel compartidos):** menos archivos, pero acopla negocio, API y base de datos; los tests unitarios necesitan PostgreSQL.
- **Un solo modelo SQLModel para tabla, dominio y API:** rápido de escribir, pero expone campos internos (por ejemplo `password_hash`) y cualquier cambio de esquema rompe la API.

## Consecuencias
- Más archivos y código de mapeo; se compensa con tests unitarios rápidos de dominio y casos de uso con repositorios en memoria (fakes), sin Docker.
- Cambiar una pieza (Redis, hashing, framework web) implica tocar un adaptador y el `bootstrap`, no el negocio.
- Las reglas que dependen de atomicidad (cupo, solape de ponente) se expresan como operaciones del puerto implementadas con SQL atómico o restricciones en el adaptador de persistencia, y se prueban con tests de integración contra PostgreSQL.
- Es un costo de arranque real para un plazo de 5 días; se mitiga creando la estructura y un caso de uso completo (`auth`) el primer día como plantilla para el resto.
