import asyncio
from uuid import uuid4

from app.core.execution_repository import execution_repository
from app.core.logging import logger, trace_id_var
from app.core.orchestrator import MAX_TOTAL_STEPS, build_orchestrator_graph
from app.schemas.orchestrator import ExecuteTaskResponse
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post(
    "/task/{trace_id}/retry", response_model=ExecuteTaskResponse, summary="Re-execute a failed task"
)
async def retry_execution(trace_id: str):
    execution = await execution_repository.get_execution_by_trace_id(trace_id)

    if not execution:
        return HTTPException(status_code=404, detail="Execturion not found")

    trace_id = trace_id_var.get() or str(uuid4())
    task_id = str(uuid4())
    task_description = execution.task_description
    logger.info("Retrying task %s: %s", task_id, task_description[:100])

    graph = build_orchestrator_graph()
    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                {
                    "task_description": task_description,
                    "step_index": 0,
                    "total_steps": 0,
                    "max_steps": MAX_TOTAL_STEPS,
                    "trace_id": trace_id,
                }
            ),
            timeout=600.0,
        )
    except TimeoutError:
        logger.error("Task %s timed out", task_id)
        raise HTTPException(status_code=504, detail="Task execution timed out")

    return ExecuteTaskResponse(
        status="success",
        task_id=task_id,
        objective=result.get("objective", ""),
        plan=result.get("plan"),
        research_findings=result.get("research_findings"),
        data_results=result.get("data_results"),
        report=result.get("report"),
        error=result.get("error"),
        total_steps=result.get("total_steps", 0),
    )
