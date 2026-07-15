from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import BaseResponse


class ExecutionSummary(BaseModel):
    id: str
    trace_id: str
    task_description: str
    objective: str | None
    status: str
    total_steps: int
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExecutionDetail(ExecutionSummary):
    steps: list["StepDetail"] = []
    llm_calls: list["LLMCallDetail"] = []
    tool_calls: list["ToolCallDetail"] = []
    report: str | None


class StepDetail(BaseModel):
    id: str
    execution_id: str
    trace_id: str
    agent_name: str
    step_type: str | None
    input_summary: str | None
    output_summary: str | None
    status: str
    error: str | None
    latency_ms: int | None
    created_at: datetime


class LLMCallDetail(BaseModel):
    id: str
    execution_id: str
    step_id: str | None
    trace_id: str
    agent_name: str
    prompt_preview: str | None
    system_prompt: str | None
    user_prompt: str | None
    response: str | None
    model: str | None
    latency_ms: int | None
    estimated_tokens_input: int | None
    estimated_tokens_output: int | None
    created_at: datetime


class ToolCallDetail(BaseModel):
    id: str
    execution_id: str
    step_id: str | None
    trace_id: str
    tool_name: str
    status: str
    input: str | None
    output_preview: str | None
    error: str | None
    latency_ms: int | None
    created_at: datetime


class ExecutionMetrics(BaseModel):
    execution_id: str
    trace_id: str
    total_duration_ms: int | None
    total_llm_calls: int
    total_tool_calls: int
    total_steps: int
    total_tokens_input: int
    total_tokens_output: int
    estimated_cost_usd: float
    avg_step_latency_ms: float | None
    avg_llm_latency_ms: float | None
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
