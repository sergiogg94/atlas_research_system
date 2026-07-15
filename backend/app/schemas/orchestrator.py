from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class ExecuteTaskRequest(BaseModel):
    task_description: str = Field(..., min_length=10, max_length=2000)


class ExecuteTaskResponse(BaseResponse):
    task_id: str
    objective: str
    plan: dict | None
    research_findings: list | None
    data_results: list | None
    report: str | None
    error: str | None
    total_steps: int
