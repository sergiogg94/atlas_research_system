from datetime import datetime
from typing import Optional

from app.schemas.base import BaseResponse
from pydantic import BaseModel


class ExecutionSummary(BaseModel):
    id: str
    trace_id: str
    task_description: str
    objective: Optional[str]
    status: str
    total_steps: int
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ExecutionDetail(ExecutionSummary):
    steps: list["StepDetail"] = []
    llm_calls: list["LLMCallDetail"] = []
    tool_calls: list["ToolCallDetail"] = []
    report: Optional[str]


class StepDetail(BaseModel):
    id: str
    execution_id: str
    trace_id: str
    agent_name: str
    step_type: Optional[str]
    input_summary: Optional[str]
    output_summary: Optional[str]
    status: str
    error: Optional[str]
    latency_ms: Optional[int]
    created_at: datetime


class LLMCallDetail(BaseModel):
    id: str
    execution_id: str
    step_id: Optional[str]
    trace_id: str
    agent_name: str
    prompt_preview: Optional[str]
    system_prompt: Optional[str]
    user_prompt: Optional[str]
    response: Optional[str]
    model: Optional[str]
    latency_ms: Optional[int]
    estimated_tokens_input: Optional[int]
    estimated_tokens_output: Optional[int]
    created_at: datetime


class ToolCallDetail(BaseModel):
    id: str
    execution_id: str
    step_id: Optional[str]
    trace_id: str
    tool_name: str
    status: str
    input: Optional[str]
    output_preview: Optional[str]
    error: Optional[str]
    latency_ms: Optional[int]
    created_at: datetime


class ExecutionMetrics(BaseModel):
    execution_id: str
    trace_id: str
    total_duration_ms: Optional[int]
    total_llm_calls: int
    total_tool_calls: int
    total_steps: int
    total_tokens_input: int
    total_tokens_output: int
    estimated_cost_usd: float
    avg_step_latency_ms: Optional[float]
    avg_llm_latency_ms: Optional[float]
    error_count: int


class ExecutionListResponse(BaseResponse):
    executions: list[ExecutionSummary]
    total: int
    page: int
    page_size: int


class ExecutionDetailResponse(BaseResponse):
    execution: ExecutionDetail


class ExecutionMetricsResponse(BaseResponse):
    metrics: ExecutionMetrics
