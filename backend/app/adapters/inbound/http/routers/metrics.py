from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.adapters.inbound.http.dependencies import get_http_config

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    """Métricas en formato Prometheus. No se publica por nginx: solo la red interna las scrapea."""
    registry = get_http_config(request).metrics_registry
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
