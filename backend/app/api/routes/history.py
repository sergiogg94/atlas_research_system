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
    status: str = Query(None, regex="^(pending|running|completed|failed|timeout)$"),
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
    "/task/{trce_id}",
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
            steps=[
                StepDetail(
                    id=str(s.id),
                    execution_id=s.execution_id,
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
                    execution_id=c.execution_id,
                    step_id=c.step_id,
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
                    id=t.id,
                    execution_id=t.execution_id,
                    step_id=t.step_id,
                    trace_id=t.trace_id,
                    tool_name=t.tool_name,
                    status=t.status,
                    input=t.input,
                    output_preview=t.output_preview,
                    error=t.error,
                    latency_ms=t.latency_ms,
                    created_at=t.created_at,
                )
                for t in tool_calls
            ],
        )
    )
