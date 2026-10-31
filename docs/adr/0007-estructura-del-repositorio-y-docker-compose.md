# ADR 0007: Estructura del repositorio y orquestación con Docker Compose

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
El PRD exige repositorio Git con backend y frontend en carpetas separadas, READMEs separados, Dockerfiles por parte y Docker Compose con backend, frontend y base de datos.

## Decisión
Monorepo con esta estructura:

```
tusdatos/
├── backend/          # FastAPI (arquitectura hexagonal, ADR 0010), Dockerfile, README.md, pyproject.toml (uv)
├── frontend/         # React + Vite, Dockerfile, README.md
├── docs/             # prd.pdf, spec.md, tdd.md, adr/
├── observability/    # configs de Alloy, Prometheus y Grafana (perfil opcional)
├── docker-compose.yml
└── .env.example
```

- Servicios de Compose: `db` (PostgreSQL), `redis`, `backend`, `frontend`. Healthchecks en `db` y `redis`; el backend espera a `db` saludable y ejecuta migraciones al iniciar.
- Dockerfile del backend multi-stage con `uv`, usuario no root. Dockerfile del frontend multi-stage: build con Node y servido con nginx, que también hace proxy de `/api` al backend.
- Servicios opcionales bajo el perfil `observability` (Loki, Alloy, Prometheus, Grafana), con su configuración en `observability/` (ADR 0009). No se levantan con el `docker compose up` normal.
- Toda la configuración por variables de entorno; `.env` fuera de Git, `.env.example` versionado.

## Alternativas
- **Dos repositorios:** el PRD pide uno solo con carpetas separadas.

## Consecuencias
- Un solo `docker compose up --build` levanta todo el entorno.
- El proxy de nginx evita problemas de CORS en el entorno de Compose.
