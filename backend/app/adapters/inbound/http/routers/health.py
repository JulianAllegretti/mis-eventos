from fastapi import APIRouter, Depends, Response, status

from app.adapters.inbound.http.dependencies import AppContainer, get_container
from app.adapters.inbound.http.mappers.health import to_readiness_response
from app.adapters.inbound.http.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=LivenessResponse, summary="Liveness")
async def health() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness: PostgreSQL es crítico; Redis degrada pero no falla",
)
async def ready(
    response: Response, container: AppContainer = Depends(get_container)
) -> ReadinessResponse:
    report = await container.check_readiness.execute()
    if report.status == "unavailable":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return to_readiness_response(report)
