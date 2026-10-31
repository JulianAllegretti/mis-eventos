# ADR 0008: Cierre automático de eventos vencidos

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
Un evento `published` pasa a `finished` cuando termina. Sin un mecanismo automático, dependería de que el organizador lo marque a mano y los eventos vencidos seguirían aceptando inscripciones.

## Decisión
Dos capas que se complementan:

1. **Tarea periódica en el backend.** Una tarea asyncio, iniciada en el `lifespan` de FastAPI, se ejecuta cada `FINISH_JOB_INTERVAL_SECONDS` (60 por defecto) y corre:
   `UPDATE events SET status = 'finished', closed_at = now(), closed_by_id = NULL, closed_source = 'scheduler' WHERE status = 'published' AND end_at < now() RETURNING id`
   - Es idempotente. Para evitar trabajo duplicado entre workers se toma `pg_try_advisory_lock`; quien no obtiene el lock omite la ejecución.
   - Con los ids devueltos, invalida la caché `events:*` y elimina el contador `event:{id}:slots` de Redis (ADR 0005).
   - Un fallo se registra y se reintenta en el siguiente ciclo; no detiene la aplicación.
2. **Estado efectivo al leer y al inscribirse.** Un evento `published` con `end_at < now()` se considera `finished` en las respuestas y la inscripción lo rechaza con 409, aunque la tarea aún no lo haya persistido. Así la corrección no depende de la puntualidad de la tarea.

### Trazabilidad del cierre
Para saber cómo y quién cerró cada evento (y poder sacar estadísticas), `events` guarda tres campos, que se llenan también al cancelar:

| Campo | Tipo | Significado |
|---|---|---|
| `closed_at` | timestamp con zona, nulo | Momento real del cierre. En el cierre automático es cuando corrió la tarea, que puede diferir de `end_at`. |
| `closed_by_id` | FK a `users`, nulo | Usuario que cerró el evento; nulo si lo cerró el sistema. |
| `closed_source` | enum `manual` \| `scheduler`, nulo | Origen del cierre. |

- Se escriben en la misma sentencia que cambia el estado, así nunca quedan inconsistentes con `status`.
- Restricción `CHECK`: `closed_at`, `closed_source` y `status IN ('finished','cancelled')` van juntos (los tres nulos si el evento está abierto; `closed_by_id` nulo si y solo si `closed_source = 'scheduler'`).
- Mientras la tarea no haya persistido el cierre, el estado efectivo `finished` no tiene `closed_*`; los campos se llenan cuando la tarea corre.
- Estos campos no se modifican después del cierre.

Reglas adicionales:
- El organizador dueño o un admin puede finalizar un evento antes de tiempo (`published → finished`), con `closed_source = 'manual'` y su id en `closed_by_id`.
- Los borradores no se cierran automáticamente; si su fecha pasa, no pueden publicarse (validación de inicio en el futuro).
- Las sesiones no tienen estado propio; se derivan del evento.

## Alternativas
- **Contenedor de cron externo o `pg_cron`:** más piezas que desplegar y configurar para una tarea de una sola sentencia.
- **Celery/APScheduler con broker:** excesivo para este caso.
- **Solo cálculo al leer, sin persistir:** funciona, pero no permite filtrar por estado en SQL de forma simple ni deja el dato consistente.
- **Solo tarea, sin estado efectivo:** hay una ventana de hasta 60 s con eventos vencidos aceptando inscripciones.

## Consecuencias
- Sin infraestructura nueva. El retraso máximo de persistencia es el intervalo configurado.
- Si el servicio de backend está caído, la tarea se pone al día al reiniciar y el estado efectivo cubre el intervalo.
- **Pruebas:** la función de cierre se expone como una función invocable para testearla sin esperar al temporizador; casos: evento vencido se cierra con `closed_source = 'scheduler'` y `closed_by_id` nulo, cierre manual guarda el usuario, evento en curso no, borrador no, idempotencia, invalidación de caché, rechazo de inscripción al vencer sin haber corrido la tarea y respeto de la restricción `CHECK`.
