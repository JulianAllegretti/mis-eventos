# Backend — Mis Eventos

API REST con FastAPI, PostgreSQL y Redis. Arquitectura hexagonal (puertos y adaptadores): ver `../docs/adr/0010-arquitectura-hexagonal-del-backend.md` y `../docs/tdd.md`.

## Estructura

```
app/
├── domain/        # entidades y reglas puras (sin frameworks)
├── application/   # casos de uso y puertos (inbound / outbound)
├── adapters/
│   ├── inbound/   # http (FastAPI), jobs
│   └── outbound/  # persistence, security, cache, system, observability
└── bootstrap/     # configuración y cableado de dependencias
```

## Configuración

Desde la raíz del repositorio:

```bash
cp .env.example .env
# edita .env: JWT_SECRET (mín. 32 caracteres), POSTGRES_PASSWORD, ADMIN_PASSWORD
```

## Ejecutar

```bash
docker compose up --build        # db + redis + backend (aplica migraciones al arrancar)
```

- API: http://localhost:8000 · Swagger: http://localhost:8000/docs
- Salud: `GET /health` (liveness) y `GET /health/ready` (readiness)
- Si `ADMIN_EMAIL` y `ADMIN_PASSWORD` están definidos, se crea el primer administrador al arrancar.

## Pruebas y calidad

Todo corre dentro de contenedores con Python 3.14; no hace falta instalar nada local.

```bash
docker compose --profile test run --rm backend-test                      # todas las pruebas
docker compose --profile test run --rm backend-test pytest tests/unit tests/api   # sin PostgreSQL
docker compose --profile test run --rm backend-test pytest --cov=app --cov-report=term-missing
docker compose --profile test run --rm backend-test lint-imports          # reglas de arquitectura
docker compose --profile test run --rm backend-test ruff check .
docker compose --profile test run --rm backend-test mypy app
```

Las pruebas de `tests/integration` necesitan PostgreSQL (el perfil `test` lo usa); sin `TEST_DATABASE_URL` se omiten.

## Migraciones

```bash
docker compose run --rm backend alembic upgrade head
docker compose --profile test run --rm backend-test alembic revision -m "descripcion"
```

## Auth

El login fija la cookie `access_token` (`HttpOnly`, `SameSite=Lax`, `Secure` según `COOKIE_SECURE`) y no devuelve el token. Las peticiones que modifican datos y traen la cookie deben venir de un origen en `ALLOWED_ORIGINS`.
