from app.core.execution_repository import execution_repository
from app.schemas.stats import ExecutionStats, StatsResponse
from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/stats",
    summary="Aggregated execution statistics",
    response_model=StatsResponse,
)
async def get_execution_stats() -> StatsResponse:
    stats = ExecutionStats(**await execution_repository.get_stats())

    return StatsResponse(status="success", stats=stats)
