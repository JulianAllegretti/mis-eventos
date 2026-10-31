# ADR 0002: PostgreSQL con SQLModel y Alembic

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
El dominio es relacional (eventos, sesiones, ponentes, usuarios, inscripciones) y requiere integridad y control de concurrencia en la capacidad.

## Decisión
- **PostgreSQL** como base de datos, con driver `psycopg` (v3).
- **SQLModel** sobre SQLAlchemy 2.x para los modelos de tabla; consultas complejas con SQLAlchemy directamente. SQLModel queda confinado al adaptador `adapters/outbound/persistence`: el dominio usa `dataclasses` y se traduce con mappers (ADR 0010).
- **Alembic** para migraciones; el esquema nunca se crea con `create_all` fuera de tests.
- Todas las consultas usan **parámetros ligados**. La búsqueda por nombre usa `ILIKE` con el patrón como parámetro, escapando `%` y `_`.
- Control de cupo con una actualización condicional atómica sobre `events.registered_count` (`... WHERE registered_count < capacity`) y restricción única `(user_id, event_id)`. PostgreSQL es la autoridad final del cupo; Redis solo actúa como filtro previo (ADR 0005). Para operaciones que modifican varias filas (por ejemplo cancelar un evento) se usa `SELECT ... FOR UPDATE`.

## Alternativas
- **MongoDB:** permitido por el PRD, pero las restricciones únicas y las transacciones sobre capacidad son más naturales en SQL.
- **Concatenar la consulta con f-strings** (sugerido en un comentario del PRD): rechazado, permite inyección SQL; el supuesto de "overhead" de los parámetros ligados no se sostiene.

## Consecuencias
- Integridad garantizada por claves foráneas, `CHECK` (capacidad ≥ 1, fin > inicio) y únicos.
- Migraciones reproducibles; el contenedor del backend ejecuta `alembic upgrade head` al arrancar.
