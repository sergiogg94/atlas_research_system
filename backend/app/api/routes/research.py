import asyncio

from app.core.agents.research import build_research_graph
from app.core.logging import logger
from app.schemas.research import ResearchRequest, ResearchResponse
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post(
    "/research",
    response_model=ResearchResponse,
    summary="Apply Research Agent",
    description=(
        "Research an objective using the Research Agent, "
        + "which performs a series of steps to gather information and insights."
    ),
)
async def create_plan(request: ResearchRequest):
    logger.info(
        "Received research request: objective_len=%d, steps_count=%d",
        len(request.objective),
        len(request.steps),
    )
    graph = build_research_graph()

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                {
                    "objective": request.objective,
                    "steps": request.steps,
                    "current_step": 0,
                    "findings": [],
                }
            ),
            timeout=600,  # 10 minutes timeout
        )
    except TimeoutError:
        logger.error("Research Agent timed out")
        raise HTTPException(status_code=504, detail="Research Agent timed out")

    if result.get("error"):
        logger.error("Research Agent error: %s", result["error"])
        raise HTTPException(status_code=400, detail=result["error"])

    logger.info(
        "Research completed: objective=%s, findings_count=%d, total_steps=%d",
        result["objective"],
        len(result.get("findings", [])),
        result["current_step"],
    )

    return ResearchResponse(
        status="success",
        objective=result["objective"],
        findings=result.get("findings", []),
        total_steps=result["current_step"],
    )
