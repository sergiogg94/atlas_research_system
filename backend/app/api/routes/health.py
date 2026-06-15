import redis.asyncio as redis
from app.config import Settings, get_settings
from app.core.database import engine
from app.schemas.base import BaseResponse
from fastapi import APIRouter, Depends
from sqlalchemy import text

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
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception as e:
        services["database"] = "unhealthy"
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        services=services,
    )
