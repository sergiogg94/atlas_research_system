from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from app.core.execution_repository import execution_repository
from app.core.logging import (
    agent_name_var,
    trace_context,
    trace_id_var,
    trace_step,
)
from app.core.middleware import TraceIDMiddleware
from app.models.execution import Execution, ExecutionStatus
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse


class TestTraceContext:
    def test_sets_and_clears_contextvars(self):
        assert trace_id_var.get() == ""
        assert agent_name_var.get() == ""

        with trace_context("test-trace", "test-agent"):
            assert trace_id_var.get() == "test-trace"
            assert agent_name_var.get() == "test-agent"

        assert trace_id_var.get() == ""
        assert agent_name_var.get() == ""

    def test_nested_context_restores_previous(self):
        with trace_context("outer", "outer-agent"):
            assert trace_id_var.get() == "outer"
            with trace_context("inner", "inner-agent"):
                assert trace_id_var.get() == "inner"
                assert agent_name_var.get() == "inner-agent"
            assert trace_id_var.get() == "outer"
            assert agent_name_var.get() == "outer-agent"


class TestTraceStep:
    @pytest.mark.asyncio
    async def test_adds_latency_to_result(self):
        @trace_step("test_agent")
        async def my_node(state):
            return {"result": "ok"}

        result = await my_node({"trace_id": "test"})
        assert result["result"] == "ok"
        assert "last_step_latency_ms" in result
        assert isinstance(result["last_step_latency_ms"], int)
        assert result["last_step_latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_propagation_on_exception(self):
        @trace_step("failing_agent")
        async def failing_node(state):
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await failing_node({"trace_id": "test"})


class TestTraceIDMiddleware:
    @pytest.mark.asyncio
    async def test_assigns_trace_id_when_missing(self):
        async def dummy(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[], middleware=[])
        app.router.add_route("/test", dummy, methods=["GET"])
        app.add_middleware(TraceIDMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/test")
            assert "X-Trace-ID" in response.headers
            assert response.headers["X-Trace-ID"] != ""

    @pytest.mark.asyncio
    async def test_preserves_existing_trace_id(self):
        async def dummy(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[], middleware=[])
        app.router.add_route("/test", dummy, methods=["GET"])
        app.add_middleware(TraceIDMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/test", headers={"X-Trace-ID": "custom-trace"})
            assert response.headers["X-Trace-ID"] == "custom-trace"


@pytest.mark.usefixtures("mock_db")
class TestExecutionRepository:
    @pytest.fixture
    def mock_db(self):
        with patch("app.core.execution_repository.SessionLocal") as mock_maker:
            session = AsyncMock()
            mock_maker.return_value = session
            session.__aenter__.return_value = session

            session.add = MagicMock()
            session.get = AsyncMock(return_value=None)

            execute_result = MagicMock()
            scalars_result = MagicMock()
            scalars_result.all.return_value = []
            execute_result.scalars.return_value = scalars_result
            execute_result.scalar_one_or_none.return_value = None
            execute_result.scalar.return_value = 0
            session.execute = AsyncMock(return_value=execute_result)

            yield session

    @pytest.mark.asyncio
    async def test_create_execution(self, mock_db):
        execution = await execution_repository.create_execution(
            trace_id="trace-1", task_description="Test task"
        )

        assert execution.trace_id == "trace-1"
        assert execution.task_description == "Test task"
        assert execution.status == ExecutionStatus.RUNNING
        assert mock_db.add.called
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_execution(self, mock_db):
        exec_id = uuid4()
        mock_exec = MagicMock(spec=Execution)
        mock_exec.id = exec_id
        mock_exec.status = ExecutionStatus.RUNNING
        mock_db.get.return_value = mock_exec

        await execution_repository.update_execution(
            execution_id=exec_id,
            status=ExecutionStatus.COMPLETED,
            report="Final report",
        )

        assert mock_exec.status == ExecutionStatus.COMPLETED
        assert mock_exec.report == "Final report"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_execution_not_found(self, mock_db):
        mock_db.get.return_value = None
        exec_id = uuid4()

        await execution_repository.update_execution(
            execution_id=exec_id, status=ExecutionStatus.COMPLETED
        )

        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_executions(self, mock_db):
        result, total = await execution_repository.list_executions()

        assert total == 0
        assert result == []
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_list_executions_with_status_filter(self, mock_db):
        result, total = await execution_repository.list_executions(status="completed")

        assert total == 0
        assert result == []

    @pytest.mark.asyncio
    async def test_add_step(self, mock_db):
        exec_id = uuid4()
        step = await execution_repository.add_step(
            {
                "execution_id": exec_id,
                "trace_id": "trace-1",
                "agent_name": "test_agent",
                "step_type": "test",
            }
        )

        assert mock_db.add.called
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_llm_call(self, mock_db):
        exec_id = uuid4()
        call = await execution_repository.add_llm_call(
            {
                "execution_id": exec_id,
                "trace_id": "trace-1",
                "agent_name": "test_agent",
                "prompt_preview": "test prompt",
            }
        )

        assert mock_db.add.called
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_tool_call(self, mock_db):
        exec_id = uuid4()
        record = await execution_repository.add_tool_call(
            {
                "execution_id": exec_id,
                "trace_id": "trace-1",
                "tool_name": "web_search",
                "input": {"query": "test"},
            }
        )

        assert mock_db.add.called
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_execution_by_trace_id_found(self, mock_db):
        exec_id = uuid4()
        mock_exec = MagicMock(spec=Execution)
        mock_exec.id = exec_id
        mock_exec.trace_id = "trace-1"

        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = mock_exec
        mock_db.execute.return_value = execute_result

        execution = await execution_repository.get_execution_by_trace_id("trace-1")
        assert execution is not None
        assert execution.trace_id == "trace-1"
        assert execution.id == exec_id

    @pytest.mark.asyncio
    async def test_get_execution_by_trace_id_not_found(self, mock_db):
        execution = await execution_repository.get_execution_by_trace_id("nonexistent")
        assert execution is None

    @pytest.mark.asyncio
    async def test_get_steps(self, mock_db):
        exec_id = uuid4()
        mock_step = MagicMock()
        mock_step.execution_id = exec_id

        execute_result = MagicMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = [mock_step]
        execute_result.scalars.return_value = scalars_result
        mock_db.execute.return_value = execute_result

        steps = await execution_repository.get_steps(exec_id)
        assert len(steps) == 1
        assert steps[0].execution_id == exec_id

    @pytest.mark.asyncio
    async def test_get_llm_calls(self, mock_db):
        exec_id = uuid4()
        mock_call = MagicMock()
        mock_call.execution_id = exec_id

        execute_result = MagicMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = [mock_call]
        execute_result.scalars.return_value = scalars_result
        mock_db.execute.return_value = execute_result

        calls = await execution_repository.get_llm_calls(exec_id)
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_get_tool_calls(self, mock_db):
        exec_id = uuid4()
        mock_record = MagicMock()
        mock_record.execution_id = exec_id

        execute_result = MagicMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = [mock_record]
        execute_result.scalars.return_value = scalars_result
        mock_db.execute.return_value = execute_result

        calls = await execution_repository.get_tool_calls(exec_id)
        assert len(calls) == 1
