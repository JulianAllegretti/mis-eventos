# ADR 0009: Observabilidad con logs estructurados, métricas y stack Grafana opcional

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
El backend tiene lógica sensible a la concurrencia (cupos, Redis, tarea de cierre). Sin logs consultables ni métricas es difícil depurar o medir. El stack de observabilidad no debe volver pesado el `docker compose up` normal.

## Decisión

### En la aplicación (siempre activo)
- **Logs JSON a stdout** con `structlog` (o `logging` con formateador JSON). Campos fijos: `timestamp`, `level`, `logger`, `message`, `request_id`, `user_id` (si hay sesión), `method`, `path`, `status`, `duration_ms`.
- **`request_id`:** un middleware lo toma del header `X-Request-ID` o genera un UUID, lo agrega al contexto de logs y lo devuelve en la respuesta.
- **Datos que nunca se registran:** contraseñas, cookies, tokens, cuerpos de petición completos ni emails. Se registra `user_id`.
- **`/health`** (liveness) y **`/health/ready`** (comprueba PostgreSQL; Redis se reporta como `degraded`, no como fallo).
- **Métricas Prometheus en `/metrics`** con `prometheus-client`:
  - HTTP: peticiones por ruta, método y estado; histograma de latencia (usando la plantilla de ruta, no la URL con ids, para evitar cardinalidad alta).
  - Negocio: `registrations_total{result="ok|full|duplicate|error"}`, `redis_slot_filter_total{result="allowed|rejected|bypassed"}`, `redis_slot_compensations_total`, `events_closed_total{source="scheduler|manual"}`, `finish_job_runs_total{result}`, `finish_job_last_success_timestamp`.
- `/metrics` no se expone por el proxy de nginx hacia el exterior; solo es accesible dentro de la red de Docker.

### Stack local (opcional, perfil de Compose)
Servicios bajo el perfil `observability`, que se levanta con `docker compose --profile observability up`:
- **Loki:** almacena los logs.
- **Grafana Alloy:** recolecta los logs de los contenedores (vía el socket de Docker, en solo lectura) y los envía a Loki. Se usa Alloy porque Promtail está descontinuado.
- **Prometheus:** hace scrape de `backend:8000/metrics`.
- **Grafana:** con datasources de Loki y Prometheus y un dashboard base aprovisionados desde archivos en `observability/`. El acceso por defecto es solo `localhost`, con credenciales tomadas de variables de entorno.

Estructura:
```
observability/
├── alloy/config.alloy
├── prometheus/prometheus.yml
└── grafana/provisioning/{datasources,dashboards}/
```

## Alternativas
- **Solo logs en stdout:** más simple, pero sin consulta ni métricas.
- **ELK/OpenSearch:** mucho más pesado que Loki para este tamaño.
- **OpenTelemetry con trazas (Tempo):** útil en sistemas distribuidos; excesivo para un monolito con un backend y el plazo de la prueba. Se deja como evolución futura.
- **Stack siempre activo en el Compose principal:** consume recursos y ralentiza el arranque para quien solo quiere correr la app.

## Consecuencias
- La app produce telemetría útil aunque el stack no esté levantado.
- Cuatro contenedores más solo cuando se pide el perfil; el socket de Docker montado en Alloy es un riesgo aceptable solo en desarrollo local y debe documentarse así.
- Las etiquetas de métricas deben mantenerse con baja cardinalidad.
- **Pruebas:** el middleware añade y propaga `request_id`; los logs no contienen campos sensibles; `/metrics` expone las métricas de negocio tras una inscripción y un cierre; `/health/ready` reporta `degraded` con Redis caído y falla con PostgreSQL caído.
