from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.core.orchestrator import (
    DEGRADATION_THRESHOLD,
    MAX_TOTAL_STEPS,
    _build_data_context,
    _next_agent,
    _record_execution_step,
    _sanitize_for_json,
    build_orchestrator_graph,
    check_degradation,
    check_max_steps,
    re_plan,
    route_after_check,
    route_after_replan,
    route_from_data,
    route_from_planner,
    route_from_research,
    run_data,
    run_planner,
    run_research,
    run_synthesis,
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
        {
            "step": 1,
            "action": "Define scope",
            "expected_output": "Scope doc",
            "step_type": "scoping",
        },
        {
            "step": 2,
            "action": "Gather recent information",
            "expected_output": "Report",
            "step_type": "research",
        },
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
    "trace_id": "test-trace",
}


@pytest.fixture(autouse=True)
def mock_redis():
    with patch.object(state_manager, "save_orchestrator_state", AsyncMock()) as m:
        yield m


@pytest.fixture(autouse=True)
def mock_execution_repo():
    mock_exec = MagicMock()
    mock_exec.id = uuid4()
    with patch("app.core.orchestrator.execution_repository") as mock_repo:
        mock_repo.create_execution = AsyncMock(return_value=mock_exec)
        mock_repo.add_step = AsyncMock(return_value=MagicMock(id=uuid4()))
        mock_repo.update_execution = AsyncMock()
        mock_repo.compute_and_upsert_metrics = AsyncMock()
        yield mock_repo


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
        patch(
            "app.core.orchestrator.build_planner_graph",
            return_value=FakeCompiledGraph(planner_return),
        ),
        patch(
            "app.core.orchestrator.build_research_graph",
            return_value=FakeCompiledGraph(research_return),
        ),
        patch(
            "app.core.orchestrator.build_data_graph", return_value=FakeCompiledGraph(data_return)
        ),
        patch(
            "app.core.orchestrator.build_synthesis_graph",
            return_value=FakeCompiledGraph(synthesis_return),
        ),
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
        patch(
            "app.core.orchestrator.build_planner_graph",
            return_value=FakeCompiledGraph(planner_return),
        ),
        patch(
            "app.core.orchestrator.build_research_graph",
            return_value=FakeCompiledGraph(research_return),
        ),
        patch("app.core.orchestrator.build_data_graph", return_value=FakeCompiledGraph()),
        patch(
            "app.core.orchestrator.build_synthesis_graph",
            return_value=FakeCompiledGraph(synthesis_return),
        ),
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
        patch(
            "app.core.orchestrator.build_planner_graph",
            return_value=FakeCompiledGraph(planner_return),
        ),
        patch("app.core.orchestrator.run_research", failing_research),
        patch(
            "app.core.orchestrator.build_data_graph", return_value=FakeCompiledGraph(data_return)
        ),
        patch(
            "app.core.orchestrator.build_synthesis_graph",
            return_value=FakeCompiledGraph(synthesis_return),
        ),
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

    with patch(
        "app.core.orchestrator.build_planner_graph", return_value=FakeCompiledGraph(planner_return)
    ):
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


# =============================================================================
# Agent error paths — planner, research, data, synthesis
# =============================================================================


async def _agent_error_state():
    return {
        **INITIAL_STATE,
        "execution_id": str(uuid4()),
        "objective": "Research AI in healthcare",
        "plan_steps": [
            {
                "step": 1,
                "action": "Analyze AI adoption data",
                "expected_output": "Analysis report",
                "step_type": "analysis",
            },
        ],
    }


@pytest.mark.asyncio
async def test_run_planner_graph_exception():
    class FailingGraph:
        async def ainvoke(self, state):
            raise RuntimeError("Planner crashed")

    with patch("app.core.orchestrator.build_planner_graph", return_value=FailingGraph()):
        result = await run_planner(
            {
                "task_description": "Research AI in healthcare",
            }
        )

    assert result.get("error") is not None
    assert "Planner failed" in result["error"]


@pytest.mark.asyncio
async def test_run_planner_result_error():
    class ErrorGraph:
        async def ainvoke(self, state):
            return {"error": "Planner validation error"}

    with patch("app.core.orchestrator.build_planner_graph", return_value=ErrorGraph()):
        result = await run_planner(
            {
                "task_description": "Research AI in healthcare",
            }
        )

    assert result.get("error") is not None
    assert "Planner validation error" in result["error"]


@pytest.mark.asyncio
async def test_run_research_graph_exception():
    class FailingGraph:
        async def ainvoke(self, state):
            raise RuntimeError("Research crashed")

    state = await _agent_error_state()
    with patch("app.core.orchestrator.build_research_graph", return_value=FailingGraph()):
        result = await run_research(state)

    assert result.get("error") is not None
    assert "Research failed" in result["error"]


@pytest.mark.asyncio
async def test_run_research_result_error():
    class ErrorGraph:
        async def ainvoke(self, state):
            return {"error": "Research query failed"}

    state = await _agent_error_state()
    with patch("app.core.orchestrator.build_research_graph", return_value=ErrorGraph()):
        result = await run_research(state)

    assert result.get("error") is not None
    assert "Research query failed" in result["error"]


@pytest.mark.asyncio
async def test_run_research_skipped_without_plan_steps():
    state = {**INITIAL_STATE, "objective": "test", "plan_steps": None}
    result = await run_research(state)

    assert result.get("error") is None
    assert result.get("research_findings") is None


@pytest.mark.asyncio
async def test_run_data_graph_exception():
    class FailingGraph:
        async def ainvoke(self, state):
            raise RuntimeError("Data crashed")

    state = await _agent_error_state()
    with patch("app.core.orchestrator.build_data_graph", return_value=FailingGraph()):
        result = await run_data(state)

    assert result.get("error") is not None
    assert "Data agent failed" in result["error"]


@pytest.mark.asyncio
async def test_run_data_result_error():
    class ErrorGraph:
        async def ainvoke(self, state):
            return {"error": "SQL execution error"}

    state = await _agent_error_state()
    with patch("app.core.orchestrator.build_data_graph", return_value=ErrorGraph()):
        result = await run_data(state)

    assert result.get("error") is not None
    assert "SQL execution error" in result["error"]


@pytest.mark.asyncio
async def test_run_data_skips_when_not_needed():
    state = await _agent_error_state()
    state["plan_steps"] = [{"action": "Define scope", "step_type": "scoping"}]
    result = await run_data(state)

    assert result.get("error") is None
    assert result.get("data_results") is None


@pytest.mark.asyncio
async def test_run_synthesis_graph_exception():
    class FailingGraph:
        async def ainvoke(self, state):
            raise RuntimeError("Synthesis crashed")

    state = await _agent_error_state()
    state["report"] = None
    with patch("app.core.orchestrator.build_synthesis_graph", return_value=FailingGraph()):
        result = await run_synthesis(state)

    assert result.get("error") is not None
    assert "Synthesis failed" in result["error"]


@pytest.mark.asyncio
async def test_run_synthesis_result_error():
    class ErrorGraph:
        async def ainvoke(self, state):
            return {"error": "Synthesis validation failed"}

    state = await _agent_error_state()
    with patch("app.core.orchestrator.build_synthesis_graph", return_value=ErrorGraph()):
        result = await run_synthesis(state)

    assert result.get("error") is not None
    assert "Synthesis validation failed" in result["error"]


# =============================================================================
# Checkpoint failure
# =============================================================================


@pytest.mark.asyncio
async def test_save_checkpoint_redis_failure(mock_redis):
    mock_redis.side_effect = RuntimeError("Redis unreachable")

    state = {**INITIAL_STATE}
    result = await save_checkpoint(state)

    assert result.get("error") is not None
    assert "Checkpoint save failed" in result["error"]


# =============================================================================
# Re-plan logic
# =============================================================================


class FakeReplanProvider:
    def __init__(self, response: str | None = None):
        self.response = response or '{"decision": "abort", "reason": "testing"}'

    async def generate(self, prompt: str, system: str | None = None) -> str:
        return self.response

    async def list_models(self) -> list[str]:
        return ["fake"]


def _error_state(**overrides) -> dict:
    return {
        **INITIAL_STATE,
        "error": "Agent failed",
        "current_agent": "research",
        "execution_id": str(uuid4()),
        "consecutive_failures": 0,
        "last_failure_agent": None,
        **overrides,
    }


@pytest.mark.asyncio
async def test_replan_skipped_when_no_error():
    state = {**INITIAL_STATE, "error": None}
    result = await re_plan(state)
    assert result is state


@pytest.mark.asyncio
async def test_replan_decision_retry_same_agent():
    state = _error_state(
        consecutive_failures=1,
        last_failure_agent="research",
    )
    provider = FakeReplanProvider('{"decision": "retry", "reason": "try again"}')

    with patch("app.core.orchestrator.get_llm_provider", return_value=provider):
        result = await re_plan(state)

    assert result.get("error") is None
    assert result["consecutive_failures"] == 2  # same agent → increment
    assert result["last_failure_agent"] == "research"


@pytest.mark.asyncio
async def test_replan_decision_retry_different_agent():
    state = _error_state(
        consecutive_failures=2,
        last_failure_agent="planner",
    )
    provider = FakeReplanProvider('{"decision": "retry", "reason": "try again"}')

    with patch("app.core.orchestrator.get_llm_provider", return_value=provider):
        result = await re_plan(state)

    assert result.get("error") is None
    assert result["consecutive_failures"] == 1  # different agent → reset to 1


@pytest.mark.asyncio
async def test_replan_decision_skip():
    state = _error_state()
    provider = FakeReplanProvider('{"decision": "skip", "reason": "skip it"}')

    with patch("app.core.orchestrator.get_llm_provider", return_value=provider):
        result = await re_plan(state)

    assert result.get("error") is None
    assert result["consecutive_failures"] == 0
    assert result["last_failure_agent"] is None
    assert result["current_agent"] != "research"  # advanced to next


@pytest.mark.asyncio
async def test_replan_decision_abort():
    state = _error_state()
    provider = FakeReplanProvider('{"decision": "abort", "reason": "cannot recover"}')

    with patch("app.core.orchestrator.get_llm_provider", return_value=provider):
        result = await re_plan(state)

    assert result.get("error") is not None  # error preserved


@pytest.mark.asyncio
async def test_replan_llm_failure_defaults_to_abort():
    class BrokenProvider:
        async def generate(self, prompt, system=None):
            raise ValueError("LLM unavailable")

        async def list_models(self):
            return []

    state = _error_state()
    with patch("app.core.orchestrator.get_llm_provider", return_value=BrokenProvider()):
        result = await re_plan(state)

    assert result.get("error") is not None  # aborted, error kept


@pytest.mark.asyncio
async def test_replan_llm_returns_invalid_json():
    state = _error_state()
    provider = FakeReplanProvider("this is not json")

    with patch("app.core.orchestrator.get_llm_provider", return_value=provider):
        result = await re_plan(state)

    assert result.get("error") is not None  # defaults to abort


# =============================================================================
# Degradation detection
# =============================================================================


@pytest.mark.asyncio
async def test_check_degradation_below_threshold():
    state = {
        **INITIAL_STATE,
        "execution_id": str(uuid4()),
        "consecutive_failures": DEGRADATION_THRESHOLD - 1,
        "current_agent": "research",
    }
    result = await check_degradation(state)

    assert result.get("error") is None
    assert result is state


@pytest.mark.asyncio
async def test_check_degradation_triggers_abort():
    state = {
        **INITIAL_STATE,
        "execution_id": str(uuid4()),
        "consecutive_failures": DEGRADATION_THRESHOLD,
        "current_agent": "research",
    }
    result = await check_degradation(state)

    assert result.get("error") is not None
    assert "Aborting" in result["error"]
    assert str(DEGRADATION_THRESHOLD) in result["error"]


@pytest.mark.asyncio
async def test_check_degradation_triggers_above_threshold():
    state = {
        **INITIAL_STATE,
        "execution_id": str(uuid4()),
        "consecutive_failures": DEGRADATION_THRESHOLD + 2,
        "current_agent": "planner",
    }
    result = await check_degradation(state)

    assert result.get("error") is not None
    assert "Aborting" in result["error"]


# =============================================================================
# Max steps check
# =============================================================================


@pytest.mark.asyncio
async def test_check_max_steps_below_limit():
    state = {
        **INITIAL_STATE,
        "total_steps": MAX_TOTAL_STEPS - 1,
        "execution_id": str(uuid4()),
    }
    result = await check_max_steps(state)
    assert result.get("error") is None


@pytest.mark.asyncio
async def test_check_max_steps_at_limit():
    state = {
        **INITIAL_STATE,
        "total_steps": MAX_TOTAL_STEPS,
        "execution_id": str(uuid4()),
    }
    result = await check_max_steps(state)
    assert result.get("error") is not None
    assert "limit reached" in result["error"].lower()


# =============================================================================
# Next agent routing
# =============================================================================


def test_next_agent_unknown_current():
    assert _next_agent("unknown", {}) == "synthesis"


def test_next_agent_last_in_order():
    assert _next_agent("synthesis", {}) == "synthesis"


def test_next_agent_research_skips_data_when_not_needed():
    state = {
        "plan_steps": [{"action": "Define scope", "step_type": "scoping"}],
    }
    assert _next_agent("research", state) == "synthesis"


def test_next_agent_research_goes_to_data_when_needed():
    state = {
        "plan_steps": [{"action": "Analyze results", "step_type": "analysis"}],
    }
    assert _next_agent("research", state) == "data"


def test_next_agent_planner_goes_to_research():
    state = {"plan_steps": [{"action": "Analyze", "step_type": "analysis"}]}
    assert _next_agent("planner", state) == "research"


def test_next_agent_data_goes_to_synthesis():
    assert _next_agent("data", {}) == "synthesis"


# =============================================================================
# Routing functions
# =============================================================================


def test_route_from_planner_error():
    state = {"error": "something wrong"}
    assert route_from_planner(state) == "error"


def test_route_from_planner_ok():
    state = {"error": None}
    assert route_from_planner(state) == "research"


def test_route_from_research_error():
    state = {"error": "something wrong"}
    assert route_from_research(state) == "error"


def test_route_from_research_data_needed():
    state = {
        "error": None,
        "plan_steps": [{"action": "Analyze data", "step_type": "analysis"}],
    }
    assert route_from_research(state) == "data"


def test_route_from_research_skip_data():
    state = {
        "error": None,
        "plan_steps": [{"action": "Define scope", "step_type": "scoping"}],
    }
    assert route_from_research(state) == "synthesis"


def test_route_from_data_error():
    state = {"error": "something wrong"}
    assert route_from_data(state) == "error"


def test_route_from_data_ok():
    state = {"error": None}
    assert route_from_data(state) == "synthesis"


def test_route_after_replan_error():
    state = {"error": "failed"}
    assert route_after_replan(state) == "end"


def test_route_after_replan_known_agent():
    state = {"current_agent": "research"}
    assert route_after_replan(state) == "run_research"


def test_route_after_replan_unknown_agent():
    state = {"current_agent": "unknown"}
    assert route_after_replan(state) == "end"


# =============================================================================
# _sanitize_for_json — edge cases
# =============================================================================


def test_sanitize_for_json_passes_clean_dict():
    d = {"key": "value", "num": 42, "flag": True, "nothing": None}
    assert _sanitize_for_json(d) == d


def test_sanitize_for_json_mixed_simple_and_complex():
    """dict with both serializable and non-serializable values."""
    d = {"simple": "ok", "num": 1, "flag": False, "bad": object()}
    cleaned = _sanitize_for_json(d)
    assert cleaned["simple"] == "ok"
    assert cleaned["num"] == 1
    assert cleaned["flag"] is False
    assert isinstance(cleaned["bad"], str)


# =============================================================================
# _build_data_context — context truncation
# =============================================================================


def test_build_data_context_truncates_when_over_5000_chars():
    long_finding = {
        "step": 1,
        "query": "q",
        "summary": "x" * 6000,
    }
    state = {
        "objective": "test",
        "plan": {"objective": "plan obj"},
        "research_findings": [long_finding],
    }
    context = _build_data_context(state)
    assert len(context) <= 5000 + len("\n\n[Context truncated...]")
    assert "Context truncated" in context


def test_build_data_context_without_plan():
    state = {"objective": "test", "research_findings": []}
    context = _build_data_context(state)
    assert context.startswith("# Objective")


def test_build_data_context_without_findings():
    state = {"objective": "test", "plan": {"objective": "plan"}}
    context = _build_data_context(state)
    assert "# Plan" in context
    assert "# Research Findings" not in context


# =============================================================================
# route_after_check — fallback edge case
# =============================================================================


def test_route_after_check_falls_to_end_for_unknown_agent():
    state = {"current_agent": "unknown", "error": None}
    assert route_after_check(state) == "end"


# =============================================================================
# build_orchestrator_graph — compilation failure
# =============================================================================


@pytest.mark.asyncio
async def test_build_orchestrator_graph_compilation_failure():
    with patch(
        "app.core.orchestrator.StateGraph.compile",
        side_effect=ValueError("Graph validation error"),
    ):
        with pytest.raises(ValueError, match="Graph validation error"):
            build_orchestrator_graph()


def test_sanitize_for_json_converts_non_serializable_values():
    d = {"bad": object()}
    cleaned = _sanitize_for_json(d)
    assert isinstance(cleaned["bad"], str)
    assert "object" in cleaned["bad"]


def test_sanitize_for_json_handles_nested_dicts():
    d = {"nested": {"inner": object()}}
    cleaned = _sanitize_for_json(d)
    assert "object" in cleaned["nested"]["inner"]


def test_sanitize_for_json_handles_lists():
    d = {"items": [1, "two", object()]}
    cleaned = _sanitize_for_json(d)
    assert cleaned["items"][0] == 1
    assert cleaned["items"][1] == "two"
    assert isinstance(cleaned["items"][2], str)


def test_sanitize_for_json_handles_nested_dicts_in_lists():
    d = {"items": [{"inner": object()}, {"inner": "ok"}]}
    cleaned = _sanitize_for_json(d)
    assert "object" in cleaned["items"][0]["inner"]
    assert cleaned["items"][1]["inner"] == "ok"


# =============================================================================
# _record_execution_step — edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_record_execution_step_without_execution_id():
    state = {**INITIAL_STATE, "execution_id": None}
    result = await _record_execution_step(
        state=state,
        agent_name="test",
        step_type="test",
    )
    assert result is None


@pytest.mark.asyncio
async def test_record_execution_step_with_invalid_execution_id():
    state = {**INITIAL_STATE, "execution_id": "not-a-uuid"}
    result = await _record_execution_step(
        state=state,
        agent_name="test",
        step_type="test",
    )
    assert result is None


@pytest.mark.asyncio
async def test_record_execution_step_repository_failure():
    """Should log warning and return None when add_step raises."""
    state = {**INITIAL_STATE, "execution_id": str(uuid4())}
    mock_add_step = AsyncMock(side_effect=Exception("DB down"))

    with patch("app.core.orchestrator.execution_repository.add_step", mock_add_step):
        result = await _record_execution_step(
            state=state,
            agent_name="test",
            step_type="test",
        )

    assert result is None


# =============================================================================
# Agent early-return when state has error
# =============================================================================


@pytest.mark.asyncio
async def test_run_planner_returns_early_when_state_has_error():
    state = {"task_description": "test", "error": "prior failure"}
    result = await run_planner(state)
    assert result["error"] == "prior failure"


@pytest.mark.asyncio
async def test_run_data_returns_early_when_state_has_error():
    state = {**INITIAL_STATE, "error": "prior failure"}
    result = await run_data(state)
    assert result["error"] == "prior failure"
