import asyncio
from uuid import uuid4

from app.core.logging import logger
from app.core.orchestrator import MAX_TOTAL_STEPS, build_orchestrator_graph
from app.schemas.orchestrator import ExecuteTaskRequest, ExecuteTaskResponse
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post(
    "/execute-task",
    response_model=ExecuteTaskResponse,
    summary="Execute a complete research task end-to-end",
    description="Orchestrates Planner, research, data and synthesis agents",
)
async def execute_task(request: ExecuteTaskRequest):
    task_id = str(uuid4())
    logger.info("Starting task %s: %s", task_id, request.task_description[:100])

    graph = build_orchestrator_graph()
    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                {
                    "task_description": request.task_description,
                    "step_index": 0,
                    "total_steps": 0,
                    "max_steps": MAX_TOTAL_STEPS,
                }
            ),
            timeout=600.0,
        )
    except asyncio.TimeoutError:
        logger.error("Task %s timed out", task_id)
        raise HTTPException(status_code=504, detail="Task execution timed out")

    return ExecuteTaskResponse(
        task_id=task_id,
        objective=result.get("objective", ""),
        plan=result.get("plan"),
        research_findings=result.get("research_findings"),
        data_results=result.get("data_results"),
        report=result.get("report"),
        error=result.get("error"),
        total_steps=result.get("total_steps", 0),
    )
