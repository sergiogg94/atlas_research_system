from fastapi import APIRouter, Query, HTTPException

from app.core.execution_repository import execution_repository
from app.schemas.history import (
    ExecutionDetailResponse,
    ExecutionListResponse,
    ExecutionSummary,
    ExecutionMetricsResponse,
    ExecutionMetrics,
    ExecutionDetail,
    StepDetail,
    LLMCallDetail,
    ToolCallDetail,
)

router = APIRouter()


@router.get(
    "/tasks",
    response_model=ExecutionListResponse,
    summary="List all task executions",
)
async def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None, pattern="^(pending|running|completed|failed|timeout)$"),
):
    executions, total = await execution_repository.list_executions(
        page=page, page_size=page_size, status=status
    )

    return ExecutionListResponse(
        executions=[
            ExecutionSummary(
                id=str(e.id),
                trace_id=e.trace_id,
                task_description=e.task_description,
                objective=e.objective,
                status=e.status,
                total_steps=e.total_steps,
                error=e.error,
                started_at=e.started_at,
                completed_at=e.completed_at,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in executions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/tasks/{trace_id}",
    response_model=ExecutionDetailResponse,
    summary="Get execution detail by trace_id",
)
async def get_execution(trace_id: str):
    execution = await execution_repository.get_execution_by_trace_id(trace_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    steps = await execution_repository.get_steps(execution.id)
    llm_calls = await execution_repository.get_llm_calls(execution.id)
    tool_calls = await execution_repository.get_tool_calls(execution.id)

    return ExecutionDetailResponse(
        execution=ExecutionDetail(
            id=str(execution.id),
            trace_id=execution.trace_id,
            task_description=execution.task_description,
            objective=execution.objective,
            status=execution.status,
            total_steps=execution.total_steps,
            error=execution.error,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
            report=execution.report,
            steps=[
                StepDetail(
                    id=str(s.id),
                    execution_id=str(s.execution_id),
                    trace_id=s.trace_id,
                    agent_name=s.agent_name,
                    step_type=s.step_type,
                    input_summary=s.input_summary,
                    output_summary=s.output_summary,
                    status=s.status,
                    error=s.error,
                    latency_ms=s.latency_ms,
                    created_at=s.created_at,
                )
                for s in steps
            ],
            llm_calls=[
                LLMCallDetail(
                    id=str(c.id),
                    execution_id=str(c.execution_id),
                    step_id=str(c.step_id) if c.step_id else None,
                    trace_id=c.trace_id,
                    agent_name=c.agent_name,
                    prompt_preview=c.prompt_preview,
                    system_prompt=c.system_prompt,
                    user_prompt=c.user_prompt,
                    response=c.response,
                    model=c.model,
                    latency_ms=c.latency_ms,
                    estimated_tokens_input=c.estimated_tokens_input,
                    estimated_tokens_output=c.estimated_tokens_output,
                    created_at=c.created_at,
                )
                for c in llm_calls
            ],
            tool_calls=[
                ToolCallDetail(
                    id=str(t.id),
                    execution_id=str(t.execution_id),
                    step_id=str(t.step_id) if t.step_id else None,
                    trace_id=t.trace_id,
                    tool_name=t.tool_name,
                    status=t.status,
                    input=str(t.input) if t.input else None,
                    output_preview=t.output_preview,
                    error=t.error,
                    latency_ms=t.latency_ms,
                    created_at=t.created_at,
                )
                for t in tool_calls
            ],
        )
    )


@router.get(
    "/tasks/{trace_id}/metrics",
    response_model=ExecutionMetricsResponse,
    summary="Get execution metrics by trace_id",
)
async def get_execution_metrics(trace_id: str):
    metrics = await execution_repository.get_metrics(trace_id)

    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")

    return ExecutionMetricsResponse(
        metrics=ExecutionMetrics(
            execution_id=str(metrics.execution_id),
            trace_id=metrics.trace_id,
            total_duration_ms=metrics.total_duration_ms,
            total_llm_calls=metrics.total_llm_calls,
            total_tool_calls=metrics.total_tool_calls,
            total_steps=metrics.total_steps,
            total_tokens_input=metrics.total_tokens_input,
            total_tokens_output=metrics.total_tokens_output,
            estimated_cost_usd=metrics.estimated_cost_usd,
            avg_step_latency_ms=metrics.avg_step_latency_ms,
            avg_llm_latency_ms=metrics.avg_llm_latency_ms,
            error_count=metrics.error_count,
        )
    )
