from app.schemas.base import BaseResponse
from fastapi import APIRouter

router = APIRouter()


class HealthResponse(BaseResponse):
    version: str = "0.1.0"
    services: dict


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of the Atlas API.",
)
async def health_check():
    services = {}
    overall_status = "healthy"

    # Redis check
    # TODO: Implement actual Redis health check
    services["redis"] = "healthy"

    # Database check
    services["database"] = "no_checked"

    return HealthResponse(
        status=overall_status,
        services=services,
    )
