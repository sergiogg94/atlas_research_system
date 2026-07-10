import time
import uuid
from typing import Any, Optional

from app.core.execution_repository import execution_repository
from app.core.llm.base import LLMProvider
from app.core.logging import (
    agent_name_var,
    execution_id_var,
    logger,
    step_id_var,
    trace_id_var,
)


class _TracedLLMProvider(LLMProvider):
    def __init__(self, wrapped: LLMProvider) -> None:
        self._wrapped = wrapped

    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        execution_id = execution_id_var.get()
        trace_id = trace_id_var.get()
        agent_name = agent_name_var.get()
        step_id = step_id_var.get()

        start = time.monotonic()
        try:
            response = await self._wrapped.generate(prompt=prompt, system=system)
            elapsed_ms = int((time.monotonic() - start) * 1000)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if execution_id:
                _try_record_llm_call(
                    execution_id=execution_id,
                    trace_id=trace_id,
                    agent_name=agent_name,
                    step_id=step_id,
                    prompt=prompt,
                    system=system,
                    response=None,
                    error=str(exc),
                    latency_ms=elapsed_ms,
                )
            raise

        if execution_id:
            _try_record_llm_call(
                execution_id=execution_id,
                trace_id=trace_id,
                agent_name=agent_name,
                step_id=step_id,
                prompt=prompt,
                system=system,
                response=response,
                error=None,
                latency_ms=elapsed_ms,
            )

        return response

    async def list_models(self) -> list[str]:
        return await self._wrapped.list_models()


def _try_record_llm_call(
    execution_id: str,
    trace_id: str,
    agent_name: str,
    step_id: Optional[str],
    prompt: str,
    system: Optional[str],
    response: Optional[str],
    error: Optional[str],
    latency_ms: int,
) -> None:
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        logger.warning("Invalid execution_id in LLM call tracing: %s", execution_id)
        return

    try:
        import asyncio

        asyncio.ensure_future(
            execution_repository.add_llm_call(
                {
                    "execution_id": exec_uuid,
                    "trace_id": trace_id or "",
                    "agent_name": agent_name or "",
                    "step_id": uuid.UUID(step_id) if step_id else None,
                    "prompt_preview": (prompt or "")[:500],
                    "system_prompt": system,
                    "user_prompt": prompt,
                    "response": response if error is None else None,
                    "model": None,
                    "latency_ms": latency_ms,
                    "estimated_tokens_input": max(1, len(prompt or "") // 4),
                    "estimated_tokens_output": (
                        len(response or "") // 4 if response else 0
                    ),
                }
            )
        )
    except Exception as exc:
        logger.warning("Failed to persist LLM call: %s", exc)


def wrap_llm_provider(provider: LLMProvider) -> LLMProvider:
    return _TracedLLMProvider(provider)


class _TracedTool:
    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    @property
    def name(self) -> str:
        return self._wrapped.name

    @property
    def description(self) -> str:
        return self._wrapped.description

    async def execute(self, **kwargs: Any) -> Any:
        execution_id = execution_id_var.get()
        trace_id = trace_id_var.get()
        agent_name = agent_name_var.get()
        step_id = step_id_var.get()

        start = time.monotonic()
        try:
            result = await self._wrapped.execute(**kwargs)
            elapsed_ms = int((time.monotonic() - start) * 1000)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if execution_id:
                _try_record_tool_call(
                    execution_id=execution_id,
                    trace_id=trace_id,
                    agent_name=agent_name,
                    step_id=step_id,
                    tool_name=self._wrapped.name,
                    tool_input=kwargs,
                    output_preview=None,
                    status="error",
                    error=str(exc),
                    latency_ms=elapsed_ms,
                )
            raise

        if execution_id:
            output_str = (
                str(result.data)[:500]
                if result.success and result.data is not None
                else None
            )
            _try_record_tool_call(
                execution_id=execution_id,
                trace_id=trace_id,
                agent_name=agent_name,
                step_id=step_id,
                tool_name=self._wrapped.name,
                tool_input=kwargs,
                output_preview=output_str,
                status="success" if result.success else "error",
                error=result.error,
                latency_ms=elapsed_ms,
            )

        return result

    def input_schema(self) -> dict:
        return self._wrapped.input_schema()


def _try_record_tool_call(
    execution_id: str,
    trace_id: str,
    agent_name: str,
    step_id: Optional[str],
    tool_name: str,
    tool_input: dict,
    output_preview: Optional[str],
    status: str,
    error: Optional[str],
    latency_ms: int,
) -> None:
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        logger.warning("Invalid execution_id in tool call tracing: %s", execution_id)
        return

    try:
        import asyncio

        asyncio.ensure_future(
            execution_repository.add_tool_call(
                {
                    "execution_id": exec_uuid,
                    "trace_id": trace_id or "",
                    "tool_name": tool_name,
                    "input": tool_input,
                    "output_preview": output_preview,
                    "status": status,
                    "error": error,
                    "latency_ms": latency_ms,
                    "step_id": uuid.UUID(step_id) if step_id else None,
                }
            )
        )
    except Exception as exc:
        logger.warning("Failed to persist tool call: %s", exc)


def wrap_tool(tool: Any) -> Any:
    return _TracedTool(tool)
