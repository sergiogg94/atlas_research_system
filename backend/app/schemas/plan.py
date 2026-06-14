from pydantic import BaseModel, Field
from enum import Enum
from app.schemas.base import BaseResponse


class StepType(str, Enum):
    SCOPING = "scoping"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"


class PlanStep(BaseModel):
    step: int = Field(..., ge=1)
    action: str = Field(..., min_length=5, max_length=500)
    expected_output: str = Field(..., min_length=5, max_length=500)
    step_type: StepType


class Plan(BaseModel):
    objective: str = Field(..., min_length=5, max_length=500)
    assumptions: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(..., min_length=1, max_length=10)


class PlanRequest(BaseModel):
    task_description: str = Field(..., min_length=10, max_length=2000)


class PlanResponse(BaseResponse):
    plan: Plan
    provider: str
