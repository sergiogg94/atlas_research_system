import asyncio

from app.core.agents.planner import build_planner_graph
from app.core.logging import logger
from app.schemas.plan import PlanRequest, PlanResponse
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Generate Plan",
    description="Generate a plan based on the provided request.",
)
async def create_plan(request: PlanRequest):
    logger.info(
        "Received plan request: task_description_len=%d",
        len(request.task_description),
    )
    graph = build_planner_graph()

    try:
        result = await graph.ainvoke(
            {
                "task_description": request.task_description,
            }
        )
    except asyncio.TimeoutError:
        logger.error("Planner timed out")
        raise HTTPException(status_code=504, detail="Planner timed out")

    if result.get("error"):
        logger.error("Planner error: %s", result["error"])
        raise HTTPException(status_code=400, detail=result["error"])

    return PlanResponse(plan=result["plan"])
