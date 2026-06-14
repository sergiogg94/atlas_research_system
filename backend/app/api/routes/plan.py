from fastapi import APIRouter, HTTPException
from app.schemas.plan import PlanRequest, PlanResponse
from app.core.agents.planner import build_planner_graph

router = APIRouter()


@router.post(
    "/plan",
    response_model=PlanResponse,
    summary="Generate Plan",
    description="Generate a plan based on the provided request.",
)
async def create_plan(request: PlanRequest):
    graph = build_planner_graph()
    result = await graph.ainvoke(
        {
            "task_description": request.task_description,
        }
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return PlanResponse(plan=result["plan"], provider=result["provider"])
