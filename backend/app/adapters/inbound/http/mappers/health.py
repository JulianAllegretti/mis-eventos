from app.adapters.inbound.http.schemas.health import ReadinessResponse
from app.application.dto.read_models import ReadinessReport


def to_readiness_response(report: ReadinessReport) -> ReadinessResponse:
    return ReadinessResponse(status=report.status, checks=report.checks)
