from unittest.mock import AsyncMock, patch

import pytest
from app.core.agents.data import (
    analyze_task,
    build_data_graph,
    classify_output,
    generate_code,
    has_python_error,
    has_sql_error,
    route_execution,
)
from app.core.llm.base import LLMProvider
from app.core.tools.base import ToolResult


class FakeLLMProvider(LLMProvider):
    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["analysis text", "generated code"]
        self.call_count = 0

    async def generate(self, prompt: str, system: str | None = None) -> str:
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp

    async def list_models(self) -> list[str]:
        return ["fake"]


PYTHON_RESULT = {
    "stdout": "0    200.0\ndtype: float64",
    "stderr": "",
    "returncode": 0,
    "plots": [],
}

SQL_RESULT = {
    "columns": ["avg_cost"],
    "rows": [{"avg_cost": 250.0}],
    "row_count": 1,
}


def build_mock_tools(python_result=PYTHON_RESULT, sql_result=SQL_RESULT):
    python_tool = AsyncMock()
    python_tool.execute.return_value = ToolResult(success=True, data=python_result)
    python_tool.name = "python_executor"

    sql_tool = AsyncMock()
    sql_tool.execute.return_value = ToolResult(success=True, data=sql_result)
    sql_tool.name = "sql_query"

    def side_effect(name):
        if name == "python_executor":
            return python_tool
        if name == "sql_query":
            return sql_tool
        raise KeyError(name)

    return python_tool, sql_tool, side_effect


def build_initial_state(**overrides):
    defaults = {
        "task": "Analyze the impact of AI on healthcare costs",
        "context": "Previous research shows AI adoption is growing.",
        "code": None,
        "query": None,
        "execution_result": None,
        "error": None,
        "iteration": 0,
        "analysis": None,
    }
    defaults.update(overrides)
    return defaults


class TestDataAgent:
    @pytest.mark.asyncio
    async def test_python_only_executes_python(self):
        llm = FakeLLMProvider(
            responses=[
                "Use Python with pandas for descriptive statistics and visualization",
                "import pandas as pd\nimport numpy as np\ndf = pd.DataFrame({'costs': [100, 200, 300]})\nprint(df.mean())",
                '{"type": "python", "python_code": "import pandas as pd\\nimport numpy as np\\ndf = pd.DataFrame({\'costs\': [100, 200, 300]})\\nprint(df.mean())"}',
            ]
        )
        _, _, get_tool_side_effect = build_mock_tools()

        with (
            patch("app.core.agents.data.get_llm_provider", return_value=llm),
            patch("app.core.agents.data.get_tool", side_effect=get_tool_side_effect),
        ):
            graph = build_data_graph()
            result = await graph.ainvoke(build_initial_state())

        assert result.get("error") is None
        assert result.get("analysis") is not None
        assert result.get("code") is not None
        assert result.get("execution_result") is not None
        assert result["execution_result"]["stdout"] is not None
        assert result["iteration"] == 1

    @pytest.mark.asyncio
    async def test_sql_path(self):
        llm = FakeLLMProvider(
            responses=[
                "Use SQL to query the database to find average costs by region",
                "SELECT region, AVG(cost) FROM healthcare_data GROUP BY region",
                '{"type": "sql", "sql_query": "SELECT region, AVG(cost) FROM healthcare_data GROUP BY region"}',
            ]
        )
        _, _, get_tool_side_effect = build_mock_tools()

        with (
            patch("app.core.agents.data.get_llm_provider", return_value=llm),
            patch("app.core.agents.data.get_tool", side_effect=get_tool_side_effect),
        ):
            graph = build_data_graph()
            result = await graph.ainvoke(build_initial_state())

        assert result.get("error") is None
        assert result.get("analysis") is not None
        assert result.get("execution_result") is not None
        assert result["iteration"] == 1

    @pytest.mark.asyncio
    async def test_retry_on_error(self):
        llm = FakeLLMProvider(
            responses=[
                "Use Python to analyze",
                "print('hello')",
                '{"type": "python"}',
            ]
        )
        python_tool, _, get_tool_side_effect = build_mock_tools()
        python_tool.execute.side_effect = [
            ToolResult(success=False, error="Division by zero"),
            ToolResult(success=True, data=PYTHON_RESULT),
        ]

        with (
            patch("app.core.agents.data.get_llm_provider", return_value=llm),
            patch("app.core.agents.data.get_tool", side_effect=get_tool_side_effect),
        ):
            graph = build_data_graph()
            result = await graph.ainvoke(build_initial_state())

        assert result.get("error") is None
        assert result["iteration"] == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        llm = FakeLLMProvider(
            responses=[
                "Use Python to analyze",
                "print('hello')",
                '{"type": "python"}',
            ]
        )
        python_tool, _, get_tool_side_effect = build_mock_tools()
        python_tool.execute.return_value = ToolResult(
            success=False, error="Persistent error"
        )

        with (
            patch("app.core.agents.data.get_llm_provider", return_value=llm),
            patch("app.core.agents.data.get_tool", side_effect=get_tool_side_effect),
        ):
            graph = build_data_graph()
            result = await graph.ainvoke(build_initial_state())

        assert result.get("error") is not None
        assert result["iteration"] == 3

    @pytest.mark.asyncio
    async def test_empty_analysis_response(self):
        llm = FakeLLMProvider(
            responses=[
                "",
                "print('hello')",
                '{"type": "python"}',
            ]
        )
        _, _, get_tool_side_effect = build_mock_tools()

        with (
            patch("app.core.agents.data.get_llm_provider", return_value=llm),
            patch("app.core.agents.data.get_tool", side_effect=get_tool_side_effect),
        ):
            graph = build_data_graph()
            result = await graph.ainvoke(build_initial_state())

        assert result.get("error") is None
        assert result.get("analysis") == ""
        assert result.get("code") is not None
        assert result.get("execution_result") is not None

    @pytest.mark.asyncio
    async def test_empty_code_generation(self):
        llm = FakeLLMProvider(
            responses=[
                "Use Python to analyze",
                "",
            ]
        )
        _, _, get_tool_side_effect = build_mock_tools()

        with (
            patch("app.core.agents.data.get_llm_provider", return_value=llm),
            patch("app.core.agents.data.get_tool", side_effect=get_tool_side_effect),
        ):
            graph = build_data_graph()
            result = await graph.ainvoke(build_initial_state())

        assert result.get("error") is None
        assert result.get("analysis") is not None
        assert result.get("code") == ""
        assert result.get("execution_result") is None

    @pytest.mark.asyncio
    async def test_error_skips_analyze_but_not_generate_code(self):
        llm = FakeLLMProvider(responses=["code with fix"])
        with patch("app.core.agents.data.get_llm_provider", return_value=llm):
            state = {
                "task": "test",
                "context": "",
                "code": None,
                "query": None,
                "execution_result": None,
                "error": "Pre-existing error",
                "iteration": 0,
                "analysis": None,
            }
            result = await analyze_task(state)
            assert result.get("error") == "Pre-existing error"
            assert result.get("analysis") is None

            result2 = await generate_code(result)
            assert result2.get("code") is not None

        assert llm.call_count == 1


class TestDataRouting:
    def test_route_execution_returns_sql(self):
        assert route_execution({"code": None, "query": "SELECT ..."}) == "sql"

    def test_route_execution_returns_python_only(self):
        assert route_execution({"code": "print(1)", "query": None}) == "python_only"

    def test_route_execution_returns_both(self):
        assert route_execution({"code": "print(1)", "query": "SELECT ..."}) == "both"

    def test_route_execution_returns_failed(self):
        assert route_execution({"code": None, "query": None}) == "failed"

    def test_has_python_error_returns_success(self):
        assert (
            has_python_error({"error": None, "iteration": 0, "query": None})
            == "success"
        )

    def test_has_python_error_returns_retry(self):
        assert has_python_error({"error": "err", "iteration": 0}) == "retry"
        assert has_python_error({"error": "err", "iteration": 2}) == "retry"

    def test_has_python_error_returns_failed(self):
        assert has_python_error({"error": "err", "iteration": 3}) == "failed"
        assert has_python_error({"error": "err", "iteration": 5}) == "failed"

    def test_has_python_error_returns_sql_pending(self):
        assert has_python_error({"error": None, "query": "SELECT ..."}) == "sql_pending"

    def test_has_sql_error_returns_success(self):
        assert has_sql_error({"error": None, "iteration": 0}) == "success"

    def test_has_sql_error_returns_retry(self):
        assert has_sql_error({"error": "err", "iteration": 0}) == "retry"
        assert has_sql_error({"error": "err", "iteration": 2}) == "retry"

    def test_has_sql_error_returns_failed(self):
        assert has_sql_error({"error": "err", "iteration": 3}) == "failed"
        assert has_sql_error({"error": "err", "iteration": 5}) == "failed"


class TestClassifyOutput:
    @pytest.mark.asyncio
    async def test_classify_output_sql(self):
        llm = FakeLLMProvider(responses=['{"type": "sql", "sql_query": "SELECT 1"}'])
        with patch("app.core.agents.data.get_llm_provider", return_value=llm):
            result = await classify_output(
                {"task": "test", "code": "SELECT 1", "trace_id": "t1"}
            )
            assert result["code"] is None
            assert result["query"] == "SELECT 1"

    @pytest.mark.asyncio
    async def test_classify_output_python(self):
        llm = FakeLLMProvider(
            responses=['{"type": "python", "python_code": "print(1)"}']
        )
        with patch("app.core.agents.data.get_llm_provider", return_value=llm):
            result = await classify_output(
                {"task": "test", "code": "print(1)", "trace_id": "t1"}
            )
            assert result["code"] == "print(1)"
            assert result["query"] is None

    @pytest.mark.asyncio
    async def test_classify_output_both(self):
        llm = FakeLLMProvider(
            responses=[
                '{"type": "both", "python_code": "print(1)", "sql_query": "SELECT 1"}'
            ]
        )
        with patch("app.core.agents.data.get_llm_provider", return_value=llm):
            result = await classify_output(
                {"task": "test", "code": "mixed", "trace_id": "t1"}
            )
            assert result["code"] == "print(1)"
            assert result["query"] == "SELECT 1"

    @pytest.mark.asyncio
    async def test_classify_output_no_code(self):
        result = await classify_output({"task": "test", "code": None, "trace_id": "t1"})
        assert result["code"] is None
        assert result.get("query") is None

    @pytest.mark.asyncio
    async def test_classify_output_invalid_json(self):
        llm = FakeLLMProvider(responses=["not valid json"])
        with patch("app.core.agents.data.get_llm_provider", return_value=llm):
            result = await classify_output(
                {"task": "test", "code": "print(1)", "trace_id": "t1"}
            )
            assert result["code"] == "print(1)"
            assert result["query"] is None
