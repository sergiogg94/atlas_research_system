import asyncio
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.tracing import _try_record_llm_call, _try_record_tool_call


def _get_call_data(mock):
    """Extract the first positional arg from the mock's last call."""
    return mock.call_args[0][0]


@pytest.mark.asyncio
class TestTryRecordLLMCall:
    async def _fire(self, **overrides):
        """Call _try_record_llm_call and yield to let the background task run."""
        exec_id = overrides.get("execution_id", str(uuid4()))

        with patch("app.core.tracing.execution_repository.add_llm_call") as mock_add:
            _try_record_llm_call(
                execution_id=exec_id,
                trace_id=overrides.get("trace_id", ""),
                agent_name=overrides.get("agent_name", ""),
                step_id=overrides.get("step_id"),
                prompt=overrides.get("prompt", ""),
                system=overrides.get("system"),
                response=overrides.get("response"),
                error=overrides.get("error"),
                latency_ms=overrides.get("latency_ms", 0),
            )

            await asyncio.sleep(0)

        return mock_add

    async def test_valid_execution_id_calls_repository(self):
        exec_id = str(uuid4())
        mock_add = await self._fire(
            execution_id=exec_id,
            trace_id="trace-1",
            agent_name="test-agent",
            step_id=str(uuid4()),
            prompt="test prompt",
            system="system prompt",
            response="test response",
            error=None,
            latency_ms=100,
        )

        mock_add.assert_awaited_once()
        data = _get_call_data(mock_add)
        assert data["execution_id"] == UUID(exec_id)
        assert data["trace_id"] == "trace-1"
        assert data["agent_name"] == "test-agent"
        assert data["response"] == "test response"

    async def test_invalid_execution_id_returns_early(self):
        with patch("app.core.tracing.execution_repository.add_llm_call") as mock_add:
            _try_record_llm_call(
                execution_id="not-a-uuid",
                trace_id="",
                agent_name="",
                step_id=None,
                prompt="",
                system=None,
                response=None,
                error="test error",
                latency_ms=0,
            )

            await asyncio.sleep(0)

        mock_add.assert_not_called()

    async def test_response_is_none_when_error_present(self):
        exec_id = str(uuid4())
        mock_add = await self._fire(
            execution_id=exec_id,
            trace_id="trace-1",
            agent_name="test-agent",
            step_id=None,
            prompt="test prompt",
            system=None,
            response=None,
            error="LLM error occurred",
            latency_ms=200,
        )

        data = _get_call_data(mock_add)
        assert data["response"] is None

    async def test_step_id_is_converted_to_uuid(self):
        step_uuid = str(uuid4())
        mock_add = await self._fire(
            execution_id=str(uuid4()),
            trace_id="trace-1",
            agent_name="test-agent",
            step_id=step_uuid,
            prompt="prompt",
            system=None,
            response="response",
            error=None,
            latency_ms=50,
        )

        data = _get_call_data(mock_add)
        assert data["step_id"] == UUID(step_uuid)

    async def test_step_id_is_none(self):
        mock_add = await self._fire(
            execution_id=str(uuid4()),
            trace_id="trace-1",
            agent_name="test-agent",
            step_id=None,
            prompt="prompt",
            system=None,
            response="response",
            error=None,
            latency_ms=50,
        )

        data = _get_call_data(mock_add)
        assert data["step_id"] is None

    async def test_prompt_preview_truncated(self):
        long_prompt = "x" * 1000
        mock_add = await self._fire(
            execution_id=str(uuid4()),
            trace_id="",
            agent_name="",
            step_id=None,
            prompt=long_prompt,
            system=None,
            response="ok",
            error=None,
            latency_ms=10,
        )

        data = _get_call_data(mock_add)
        assert len(data["prompt_preview"]) == 500

    async def test_repository_failure_does_not_raise(self):
        exec_id = str(uuid4())
        with patch(
            "app.core.tracing.execution_repository.add_llm_call",
            AsyncMock(side_effect=Exception("DB down")),
        ):
            _try_record_llm_call(
                execution_id=exec_id,
                trace_id="trace-1",
                agent_name="agent",
                step_id=None,
                prompt="prompt",
                system=None,
                response=None,
                error=None,
                latency_ms=50,
            )

            await asyncio.sleep(0)

    async def test_estimated_tokens_computed(self):
        prompt = "hello world, this is a test prompt " * 10
        response = "short response"
        mock_add = await self._fire(
            execution_id=str(uuid4()),
            trace_id="",
            agent_name="",
            step_id=None,
            prompt=prompt,
            system=None,
            response=response,
            error=None,
            latency_ms=10,
        )

        data = _get_call_data(mock_add)
        assert data["estimated_tokens_input"] == max(1, len(prompt) // 4)
        assert data["estimated_tokens_output"] == len(response) // 4


@pytest.mark.asyncio
class TestTryRecordToolCall:
    async def _fire(self, **overrides):
        with patch("app.core.tracing.execution_repository.add_tool_call") as mock_add:
            _try_record_tool_call(
                execution_id=overrides.get("execution_id", str(uuid4())),
                trace_id=overrides.get("trace_id", ""),
                agent_name=overrides.get("agent_name", ""),
                step_id=overrides.get("step_id"),
                tool_name=overrides.get("tool_name", "test_tool"),
                tool_input=overrides.get("tool_input", {}),
                output_preview=overrides.get("output_preview"),
                status=overrides.get("status", "success"),
                error=overrides.get("error"),
                latency_ms=overrides.get("latency_ms", 0),
            )

            await asyncio.sleep(0)

        return mock_add

    async def test_valid_execution_id_calls_repository(self):
        exec_id = str(uuid4())
        mock_add = await self._fire(
            execution_id=exec_id,
            trace_id="trace-1",
            agent_name="agent",
            step_id=str(uuid4()),
            tool_name="web_search",
            tool_input={"query": "test"},
            output_preview="search results",
            status="success",
            error=None,
            latency_ms=150,
        )

        mock_add.assert_awaited_once()
        data = _get_call_data(mock_add)
        assert data["execution_id"] == UUID(exec_id)
        assert data["tool_name"] == "web_search"
        assert data["input"] == {"query": "test"}
        assert data["status"] == "success"
        assert data["error"] is None

    async def test_invalid_execution_id_returns_early(self):
        with patch("app.core.tracing.execution_repository.add_tool_call") as mock_add:
            _try_record_tool_call(
                execution_id="bad-uuid",
                trace_id="",
                agent_name="",
                step_id=None,
                tool_name="tool",
                tool_input={},
                output_preview=None,
                status="error",
                error="fail",
                latency_ms=0,
            )

            await asyncio.sleep(0)

        mock_add.assert_not_called()

    async def test_error_status_passed_through(self):
        mock_add = await self._fire(
            execution_id=str(uuid4()),
            trace_id="",
            agent_name="",
            step_id=None,
            tool_name="python_executor",
            tool_input={"code": "bad code"},
            output_preview=None,
            status="error",
            error="SyntaxError",
            latency_ms=5,
        )

        data = _get_call_data(mock_add)
        assert data["status"] == "error"
        assert data["error"] == "SyntaxError"
        assert data["output_preview"] is None

    async def test_step_id_conversion(self):
        step_uuid = str(uuid4())
        mock_add = await self._fire(
            execution_id=str(uuid4()),
            trace_id="",
            agent_name="",
            step_id=step_uuid,
            tool_name="tool",
            tool_input={},
            output_preview=None,
            status="success",
            error=None,
            latency_ms=0,
        )

        data = _get_call_data(mock_add)
        assert data["step_id"] == UUID(step_uuid)

    async def test_repository_failure_does_not_raise(self):
        exec_id = str(uuid4())
        with patch(
            "app.core.tracing.execution_repository.add_tool_call",
            AsyncMock(side_effect=Exception("DB down")),
        ):
            _try_record_tool_call(
                execution_id=exec_id,
                trace_id="trace-1",
                agent_name="agent",
                step_id=None,
                tool_name="tool",
                tool_input={},
                output_preview=None,
                status="success",
                error=None,
                latency_ms=10,
            )

            await asyncio.sleep(0)
