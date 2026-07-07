from unittest.mock import AsyncMock, patch

import pytest

from app.core.orchestrator import (
    MAX_TOTAL_STEPS,
    build_orchestrator_graph,
    run_planner,
    save_checkpoint,
)
from app.core.state_manager import state_manager
from test_planner import FAKE_PLAN


class FakePlanObj:
    """Wraps a dict to mimic a Pydantic model's .model_dump()."""
    def __init__(self, data: dict):
        self._data = data
    def model_dump(self) -> dict:
        return self._data


class FakeCompiledGraph:
    """Mocks a compiled langgraph StateGraph with a fixed return value."""
    def __init__(self, return_value: dict | None = None):
        self.return_value = return_value or {}
    async def ainvoke(self, state: dict) -> dict:
        return self.return_value


FAKE_PLAN_NO_ANALYSIS = {
    "objective": "Research AI in healthcare",
    "assumptions": ["AI is growing"],
    "steps": [
        {"step": 1, "action": "Define scope", "expected_output": "Scope doc", "step_type": "scoping"},
        {"step": 2, "action": "Gather recent information", "expected_output": "Report", "step_type": "research"},
    ],
}

INITIAL_STATE = {
    "task_description": "Research AI in healthcare",
    "objective": "",
    "plan": None,
    "plan_steps": None,
    "research_findings": None,
    "data_results": None,
    "report": None,
    "error": None,
    "current_agent": "",
    "step_index": 0,
    "total_steps": 0,
    "max_steps": MAX_TOTAL_STEPS,
    "checkpoint_idx": None,
    "consecutive_failures": 0,
    "last_failure_agent": None,
}


@pytest.fixture(autouse=True)
def mock_redis():
    with patch.object(state_manager, "save_orchestrator_state", AsyncMock()) as m:
        yield m


@pytest.mark.asyncio
async def test_run_planner():
    with patch(
        "app.core.orchestrator.build_planner_graph",
        return_value=FakeCompiledGraph({"plan": FakePlanObj(FAKE_PLAN)}),
    ):
        result = await run_planner({"task_description": "Research AI in healthcare"})
        assert result.get("plan") is not None
        assert result["current_agent"] == "planner"
        assert result["total_steps"] == 1


@pytest.mark.asyncio
async def test_full_pipeline_mocked():
    planner_return = {"plan": FakePlanObj(FAKE_PLAN)}
    research_return = {"findings": [{"step": 1, "query": "q", "summary": "s"}]}
    data_return = {"execution_result": {"data": [1, 2, 3]}}
    synthesis_return = {"report": "Final report text"}

    with (
        patch("app.core.orchestrator.build_planner_graph", return_value=FakeCompiledGraph(planner_return)),
        patch("app.core.orchestrator.build_research_graph", return_value=FakeCompiledGraph(research_return)),
        patch("app.core.orchestrator.build_data_graph", return_value=FakeCompiledGraph(data_return)),
        patch("app.core.orchestrator.build_synthesis_graph", return_value=FakeCompiledGraph(synthesis_return)),
    ):
        graph = build_orchestrator_graph()
        result = await graph.ainvoke(INITIAL_STATE)

    assert result.get("error") is None, f"Pipeline error: {result.get('error')}"
    assert result["report"] == "Final report text"
    assert len(result["research_findings"]) == 1
    assert result["data_results"] == {"data": [1, 2, 3]}
    assert result["plan"] == FAKE_PLAN
    assert result["current_agent"] == "synthesis"
    assert result["total_steps"] > 0


@pytest.mark.asyncio
async def test_skip_data_when_not_needed():
    planner_return = {"plan": FakePlanObj(FAKE_PLAN_NO_ANALYSIS)}
    research_return = {"findings": [{"step": 1, "query": "q", "summary": "s"}]}
    synthesis_return = {"report": "Report without data analysis"}

    with (
        patch("app.core.orchestrator.build_planner_graph", return_value=FakeCompiledGraph(planner_return)),
        patch("app.core.orchestrator.build_research_graph", return_value=FakeCompiledGraph(research_return)),
        patch("app.core.orchestrator.build_data_graph", return_value=FakeCompiledGraph()),
        patch("app.core.orchestrator.build_synthesis_graph", return_value=FakeCompiledGraph(synthesis_return)),
    ):
        graph = build_orchestrator_graph()
        result = await graph.ainvoke(INITIAL_STATE)

    assert result.get("error") is None
    assert result["report"] == "Report without data analysis"
    assert result["data_results"] is None
    assert result["current_agent"] == "synthesis"


@pytest.mark.asyncio
async def test_replan_on_error():
    planner_return = {"plan": FakePlanObj(FAKE_PLAN)}
    data_return = {"execution_result": {"data": ["recovered"]}}
    synthesis_return = {"report": "Report after replanning"}

    async def failing_research(state):
        return {**state, "error": "Research agent failed", "current_agent": "research"}

    class FakeReplanProvider:
        async def generate(self, prompt: str, system: str | None = None) -> str:
            return '{"decision": "skip", "reason": "testing recovery"}'
        async def list_models(self) -> list[str]:
            return ["fake"]

    with (
        patch("app.core.orchestrator.build_planner_graph", return_value=FakeCompiledGraph(planner_return)),
        patch("app.core.orchestrator.run_research", failing_research),
        patch("app.core.orchestrator.build_data_graph", return_value=FakeCompiledGraph(data_return)),
        patch("app.core.orchestrator.build_synthesis_graph", return_value=FakeCompiledGraph(synthesis_return)),
        patch("app.core.orchestrator.get_llm_provider", return_value=FakeReplanProvider()),
    ):
        graph = build_orchestrator_graph()
        result = await graph.ainvoke(INITIAL_STATE)

    assert result.get("error") is None, f"Unexpected error: {result.get('error')}"
    assert result["report"] == "Report after replanning"
    assert result["current_agent"] == "synthesis"


@pytest.mark.asyncio
async def test_max_steps_limit():
    planner_return = {"plan": FakePlanObj(FAKE_PLAN)}
    near_limit_state = {**INITIAL_STATE, "total_steps": MAX_TOTAL_STEPS}

    with patch("app.core.orchestrator.build_planner_graph", return_value=FakeCompiledGraph(planner_return)):
        graph = build_orchestrator_graph()
        result = await graph.ainvoke(near_limit_state)

    assert result.get("error") is not None
    assert "limit reached" in result["error"].lower()


@pytest.mark.asyncio
async def test_checkpoint_persistence(mock_redis):
    state = {**INITIAL_STATE}
    result = await save_checkpoint(state)

    assert result["checkpoint_idx"] is not None
    mock_redis.assert_awaited_once()
