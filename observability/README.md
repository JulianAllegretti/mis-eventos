# Observabilidad

Stack opcional para ver qué hace la aplicación: **métricas** (Prometheus), **logs** (Loki + Alloy) y un **panel** (Grafana). No se levanta con el `docker compose up` normal.

```bash
# 1. Define una clave de Grafana en .env (obligatoria: sin ella Grafana usaría admin/admin)
#    GRAFANA_ADMIN_PASSWORD=...

# 2. Levanta la aplicación junto con el stack
docker compose --profile observability up -d --build
```

| Servicio   | URL                      | Para qué                                              |
| ---------- | ------------------------ | ----------------------------------------------------- |
| Grafana    | http://localhost:3000    | Panel «Mis Eventos» (carpeta del mismo nombre), logs  |
| Prometheus | http://localhost:9090    | Consultas y alertas (`/alerts`)                       |
| Backend    | http://localhost:8000/metrics | Métricas en bruto                                |

Todos los puertos se publican solo en `127.0.0.1`. Usuario de Grafana: `GRAFANA_ADMIN_USER` (por defecto `admin`).

## Qué muestra el panel

- **API**: peticiones por segundo y por estado, errores 5xx, latencia p50/p95/p99 y **p95 por ruta**.
- **Inscripciones y cupos**: resultado de cada inscripción (ok, full, duplicate, rejected, error), decisiones del filtro de Redis, cupos devueltos, aciertos de caché y si Redis dejó de usarse.
- **Cierre automático**: eventos cerrados por el scheduler o a mano, antigüedad del último cierre correcto y fallos de la tarea.
- **Seguridad**: intentos de login por resultado y logins bloqueados.
- **Logs**: errores del backend y sus peticiones (JSON con `request_id`).

## Consultas útiles

```logql
{service="backend", level="error"}                       # errores
{service="backend"} | json | request_id="<id>"           # una petición concreta (X-Request-ID)
{service="backend"} | json | status >= 500               # respuestas con error
```

```promql
histogram_quantile(0.95, sum by (le, route) (rate(miseventos_http_request_duration_seconds_bucket[5m])))
sum by (result) (rate(miseventos_registrations_total[1m]))
```

## Estructura

```
observability/
├── prometheus/   prometheus.yml (scrape del backend cada 5 s) y alerts.yml
├── loki/         loki-config.yaml (almacén local, retención de 7 días)
├── alloy/        config.alloy (recolecta los logs de los contenedores → Loki)
└── grafana/      provisioning/ (fuentes de datos y proveedor de paneles) y dashboards/
```

## Seguridad y límites

- **Alloy monta `/var/run/docker.sock` en solo lectura.** Acceder al socket equivale a acceso al host: úsalo únicamente en desarrollo local.
- `/metrics` no se publica por nginx; solo la red interna lo consulta.
- Las etiquetas de métricas tienen valores cerrados (la ruta es una plantilla, nunca la URL real) y los logs no contienen contraseñas, cookies, tokens ni correos.
- No hay Alertmanager: las reglas de `alerts.yml` se consultan en Prometheus.
