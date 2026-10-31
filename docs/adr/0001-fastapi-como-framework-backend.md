# ADR 0001: FastAPI como framework del backend

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
El PRD permite FastAPI o Flask, con Python 3.14, SQLModel/SQLAlchemy, Swagger y pytest. Se necesita validación de entrada, documentación OpenAPI y autenticación con dependencias reutilizables en 5 días.

## Decisión
Usar **FastAPI** con **uv** para dependencias, ejecutado con Uvicorn.

## Alternativas
- **Flask:** más simple, pero exige agregar validación (marshmallow/pydantic) y Swagger (flask-smorest/apispec) a mano.

## Consecuencias
- OpenAPI y validación salen del código sin trabajo extra.
- El sistema de dependencias de FastAPI sirve para auth, RBAC y sesión de BD, y facilita los tests con `dependency_overrides`.
- Hay que verificar que cada dependencia tenga wheels para Python 3.14 (psycopg, argon2-cffi, pydantic-core).
