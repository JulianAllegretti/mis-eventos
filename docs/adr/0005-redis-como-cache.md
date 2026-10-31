# ADR 0005: Redis como filtro de cupos y caché de lectura

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
Dos usos justifican Redis:
1. **Concurrencia en inscripciones:** si dos usuarios intentan tomar el último cupo a la vez, solo uno debe lograrlo, y bajo mucha carga conviene rechazar rápido sin saturar PostgreSQL con bloqueos.
2. **Lecturas frecuentes:** el listado y el detalle de eventos (bonus de caching del PRD).

## Decisión

### Cupos: filtro previo en Redis, autoridad final en PostgreSQL
- Cada evento publicado tiene un contador `event:{id}:slots` con los cupos restantes.
- **Flujo de inscripción:**
  1. Un script Lua atómico decrementa el contador solo si es mayor que 0. Si no hay cupo, responde 409 sin tocar PostgreSQL.
  2. Si hubo cupo, se abre la transacción en PostgreSQL y se ejecuta una actualización condicional atómica:
     `UPDATE events SET registered_count = registered_count + 1 WHERE id = :id AND registered_count < capacity AND status = 'published'`
     seguida del insert de la inscripción, protegido por la restricción única `(user_id, event_id)`.
  3. Si PostgreSQL rechaza (evento lleno, duplicado, estado inválido o error), se **compensa** con `INCR` en Redis y se devuelve el error correspondiente.
- **PostgreSQL es siempre la autoridad:** aunque Redis diga que hay cupo, el update condicional y la restricción única deciden. Nunca se confirma una inscripción solo con Redis.
- **Cancelación de inscripción:** se libera el cupo en PostgreSQL y luego se hace `INCR` en Redis.
- **Cambios de capacidad o de estado del evento:** se reescribe el contador a `capacity - registered_count` dentro de la misma operación.
- **Reconciliación:** si la clave no existe (primer uso o reinicio de Redis) se inicializa desde PostgreSQL con `SET NX`. Una tarea periódica (cada 60 s) recalcula los contadores de eventos publicados para corregir desvíos.
- **Redis caído:** se omite el filtro y la inscripción se resuelve solo con PostgreSQL, que sigue siendo correcto.

### Caché de lectura
- Se cachean las respuestas del listado público (clave con página, tamaño y término de búsqueda) y del detalle, con TTL de 60 s.
- Se invalidan por prefijo (`events:*`) ante escrituras de eventos, sesiones e inscripciones.
- Si Redis falla, se registra una advertencia y se lee de PostgreSQL.

## Alternativas
- **Solo PostgreSQL** (update condicional o `SELECT ... FOR UPDATE`): suficiente para la corrección, pero toda la contención cae en la fila del evento bajo alta carga.
- **Redis como única fuente del cupo, con escritura posterior a PostgreSQL:** rechazado; un reinicio o un fallo entre ambos pasos produce sobreventa o cupos perdidos.
- **Caché en proceso:** inconsistente con varios workers.

## Consecuencias
- El contador de Redis puede desviarse temporalmente (fallo entre el paso 1 y la compensación); la reconciliación lo corrige y nunca compromete la integridad, porque PostgreSQL decide.
- Un cupo mostrado en el listado puede retrasarse hasta 60 s por la caché de lectura; es solo informativo.
- Un servicio más en Docker Compose, con persistencia AOF opcional.
- **Pruebas obligatorias:** un test de concurrencia con N inscripciones simultáneas contra 1 cupo (exactamente 1 éxito y N-1 respuestas 409, sin sobreventa), con Redis activo y con Redis apagado; tests de compensación ante fallo de PostgreSQL y de reconciliación.
