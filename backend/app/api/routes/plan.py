import asyncio

from app.core.agents.planner import build_planner_graph
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
    graph = build_planner_graph()

    try:
        result = await graph.ainvoke(
            {
                "task_description": request.task_description,
            }
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Planner timed out")

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return PlanResponse(plan=result["plan"], provider=result["provider"])
