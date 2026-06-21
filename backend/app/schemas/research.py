from app.schemas.base import BaseResponse
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    objective: str = Field(..., min_length=10, max_length=1000)
    steps: list[dict] = Field(..., min_length=1)


class ResearchFinding(BaseModel):
    step: int
    query: str
    summary: str


class ResearchResponse(BaseResponse):
    objective: str
    findings: list[ResearchFinding]
    total_steps: int
