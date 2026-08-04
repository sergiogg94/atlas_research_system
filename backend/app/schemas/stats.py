from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import BaseResponse


class RecentExecutionSummary(BaseModel):
    trace_id: str
    task_description: str
    status: str
    created_at: datetime


class ExecutionStats(BaseModel):
    total: int
    completed: int
    failed: int
    timeout: int
    avg_duration_ms: int
    success_rate: float
    recent_executions: list[RecentExecutionSummary]


class StatsResponse(BaseResponse):
    stats: ExecutionStats
