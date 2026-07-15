import asyncio

from app.core.agents.data import build_data_graph
from app.core.logging import logger
from app.schemas.data import DataRequest, DataResponse
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post(
    "/data",
    response_model=DataResponse,
    summary="Execute a data task",
    description="Executes a data task basedon the task description and context",
)
async def execute_data_task(request: DataRequest):
    logger.info("Recived data request")
    graph = build_data_graph()

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                {
                    "task": request.task,
                    "context": request.context,
                    "iteration": 0,
                }
            ),
            timeout=180.0,
        )
    except TimeoutError:
        logger.error("Data task timed out")
        raise HTTPException(status_code=504, detail="Data task timed out")

    return DataResponse(
        task=result["task"],
        code=result.get("code"),
        query=result.get("query"),
        result=result.get("execution_result"),
        error=result.get("error"),
        iterations=result.get("iteration", 0),
    )
