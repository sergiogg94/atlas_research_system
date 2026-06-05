from app.schemas.base import BaseResponse
from fastapi import APIRouter, Depends
from app.config import get_settings, Settings
import redis.asyncio as redis

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
async def health_check(settings: Settings = Depends(get_settings)):
    services = {}
    overall_status = "healthy"

    # Redis check
    try:
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        services["redis"] = "healthy"
        await r.close()
    except Exception as e:
        services["redis"] = "unhealthy"
        overall_status = "degraded"

    # Database check
    services["database"] = "no_checked"

    return HealthResponse(
        status=overall_status,
        services=services,
    )
