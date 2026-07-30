import asyncio
import json

from app.core.execution_repository import execution_repository
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


async def execution_event_generator(trace_id: str):
    """Generate SSE events for execution progress updates."""
    last_status = None
    last_step_count = 0

    while True:
        try:
            execution = await execution_repository.get_execution_by_trace_id(trace_id)

            if not execution:
                yield {"event": "error", "data": json.dumps({"message": "Execution not found"})}
                return

            status = str(execution.status)
            steps = await execution_repository.get_steps(execution.id)
            step_count = len(steps)

            # Only push event if something changed
            if status != last_status or step_count != last_step_count:
                last_status = status
                last_step_count = step_count

                steps_data = [
                    {
                        "id": str(s.id),
                        "agent_name": s.agent_name,
                        "step_type": s.step_type,
                        "status": s.status,
                        "latency_ms": s.latency_ms,
                        "error": s.error,
                        "created_at": str(s.created_at),
                    }
                    for s in steps
                ]
                data = {
                    "trace_id": trace_id,
                    "status": status,
                    "total_steps": getattr(execution, "total_steps", 0),
                    "steps": steps_data,
                }
                yield {"event": "progress", "data": json.dumps(data)}

            if status in ("completed", "failed", "timeout"):
                # Send final event with full detail (including metrics and report)
                metrics = await execution_repository.get_metrics(trace_id)
                data["metrics"] = {
                    "total_duration_ms": metrics.total_duration_ms if metrics else None,
                    "total_llm_calls": metrics.total_llm_calls if metrics else 0,
                    "total_tool_calls": metrics.total_tool_calls if metrics else 0,
                    "total_tokens_input": metrics.total_tokens_input if metrics else 0,
                    "total_tokens_output": metrics.total_tokens_output if metrics else 0,
                    "estimated_cost_usd": metrics.estimated_cost_usd if metrics else 0.0,
                    "error_count": metrics.error_count if metrics else 0,
                }
                data["report"] = getattr(execution, "report", None)
                yield {"event": "complete", "data": json.dumps(data)}
                return

            await asyncio.sleep(1)

        except asyncio.CancelledError:
            break
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)})}
            return


@router.get(
    "/tasks/{trace_id}/stream",
    summary="SSE endpoint that pushes execution progress updates.",
)
async def stream_execution(trace_id: str):
    return EventSourceResponse(execution_event_generator(trace_id))
