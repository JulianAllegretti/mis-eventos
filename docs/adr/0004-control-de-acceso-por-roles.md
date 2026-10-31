# ADR 0004: Control de acceso por roles (RBAC) y propiedad

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
El bonus pide roles Admin, Organizador y Asistente con permisos por rol. El requisito base solo exige estar autenticado para crear/editar.

## Decisión
- Tres roles en un `enum` de la tabla `users`: `attendee` (por defecto), `organizer`, `admin`.
- Dependencias de FastAPI: `get_current_user`, `require_role(*roles)` y `require_event_owner_or_admin`.
- Regla: crear eventos, sesiones y ponentes → `organizer` o `admin`; editar/borrar un evento → su organizador o `admin`; cambiar roles y listar usuarios → `admin`.
- Los usuarios se registran siempre como `attendee`; el registro público no permite elegir rol. El primer admin se crea con `ADMIN_EMAIL` / `ADMIN_PASSWORD` al arrancar.

## Alternativas
- **Solo autenticación (sin roles):** cumple el mínimo del PRD, pero cualquier usuario podría editar eventos ajenos.
- **Permisos granulares (ABAC o tabla de permisos):** excesivo para el tamaño del dominio.

## Consecuencias
- Reglas de autorización centralizadas y testeables.
- Se necesita un flujo para que un asistente pase a organizador (lo hace un admin).
