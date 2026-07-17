from unittest.mock import patch

import pytest
from app.core.agents.synthesis import (
    MAX_ITERATIONS,
    build_synthesis_graph,
    collect_results,
    generate_synthesis,
    synthesis_complete,
    validate_report,
)
from app.core.llm.base import LLMProvider


class FakePrompt:
    def __init__(self, template: str = "test template"):
        self.template = template

    def format(self, **kwargs):
        return self.template


class FakeSynthesisLLM(LLMProvider):
    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["Final report"]
        self.call_count = 0

    async def generate(self, prompt: str, system: str | None = None) -> str:
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp

    async def list_models(self) -> list[str]:
        return ["fake"]


BASE_STATE = {
    "objective": "test objective",
    "task_description": "test task",
    "plan": {"objective": "plan objective", "steps": []},
    "research_findings": [{"step": 1, "query": "q", "summary": "s"}],
    "data_results": [{"data": "test"}],
    "report": None,
    "error": None,
    "iteration": 0,
    "trace_id": "test-trace",
}


class TestCollectResults:
    @pytest.mark.asyncio
    async def test_returns_state_when_no_error(self):
        state = {**BASE_STATE}
        result = await collect_results(state)
        assert result == state

    @pytest.mark.asyncio
    async def test_returns_state_unchanged_when_prior_error(self):
        state = {**BASE_STATE, "error": "prev error"}
        result = await collect_results(state)
        assert result is state


class TestGenerateSynthesis:
    @pytest.mark.asyncio
    async def test_calls_llm_and_returns_report(self):
        llm = FakeSynthesisLLM()
        with (
            patch("app.core.agents.synthesis.get_llm_provider", return_value=llm),
            patch("app.core.agents.synthesis.get_prompt", return_value=FakePrompt()),
        ):
            result = await generate_synthesis({**BASE_STATE})

        assert result["report"] == "Final report"
        assert result["iteration"] == 1
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_skipped_when_prior_error(self):
        state = {**BASE_STATE, "error": "prev error"}
        llm = FakeSynthesisLLM(responses=["should not be called"])
        with patch("app.core.agents.synthesis.get_llm_provider", return_value=llm):
            result = await generate_synthesis(state)

        assert result["iteration"] == 1
        assert result.get("report") is None
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_increments_iteration_from_state(self):
        state = {**BASE_STATE, "iteration": 5}
        llm = FakeSynthesisLLM()
        with (
            patch("app.core.agents.synthesis.get_llm_provider", return_value=llm),
            patch("app.core.agents.synthesis.get_prompt", return_value=FakePrompt()),
        ):
            result = await generate_synthesis(state)

        assert result["iteration"] == 6

    @pytest.mark.asyncio
    async def test_builds_context_from_all_state_fields(self):
        llm = FakeSynthesisLLM(responses=["context_test"])
        captured = {}

        class CapturingPrompt:
            template = """template objective: {objective}
                task_description: {task_description}
                plan: {plan}
                research_findings: {research_findings}
                data_results: {data_results}"""

            def format(self, **kwargs):
                captured.update(kwargs)
                return self.template.format(**kwargs)

        with (
            patch("app.core.agents.synthesis.get_llm_provider", return_value=llm),
            patch(
                "app.core.agents.synthesis.get_prompt",
                return_value=CapturingPrompt(),
            ),
        ):
            await generate_synthesis({**BASE_STATE})

        assert captured["objective"] == "test objective"
        assert captured["task_description"] == "test task"
        assert captured["plan"] == str(BASE_STATE["plan"])
        assert captured["research_findings"] == str(BASE_STATE["research_findings"])
        assert captured["data_results"] == str(BASE_STATE["data_results"])

    @pytest.mark.asyncio
    async def test_propagates_llm_exception(self):
        class BrokenProvider(LLMProvider):
            async def generate(self, prompt, system=None):
                raise ValueError("LLM unavailable")

            async def list_models(self):
                return []

        with (
            patch(
                "app.core.agents.synthesis.get_llm_provider",
                return_value=BrokenProvider(),
            ),
            patch(
                "app.core.agents.synthesis.get_prompt",
                return_value=FakePrompt(),
            ),
        ):
            with pytest.raises(ValueError, match="LLM unavailable"):
                await generate_synthesis({**BASE_STATE})


class TestValidateReport:
    @pytest.mark.asyncio
    async def test_clears_error_on_success(self):
        state = {
            **BASE_STATE,
            "report": "valid report",
            "error": None,
            "iteration": 2,
        }
        result = await validate_report(state)
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_sets_error_when_report_is_none_at_max_iterations(self):
        state = {**BASE_STATE, "report": None, "iteration": MAX_ITERATIONS}
        result = await validate_report(state)
        assert result["error"] == "No report was generated"

    @pytest.mark.asyncio
    async def test_sets_error_when_report_is_empty_at_max_iterations(self):
        state = {**BASE_STATE, "report": "", "iteration": MAX_ITERATIONS}
        result = await validate_report(state)
        assert result["error"] == "No report was generated"

    @pytest.mark.asyncio
    async def test_does_not_set_error_when_iteration_below_max(self):
        state = {**BASE_STATE, "report": None, "iteration": 1}
        result = await validate_report(state)
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_skipped_when_prior_error(self):
        state = {**BASE_STATE, "error": "prior error", "report": "valid"}
        result = await validate_report(state)
        assert result is state


class TestSynthesisComplete:
    def test_complete_when_report_exists_and_no_error(self):
        state = {"report": "valid", "error": None, "iteration": 2}
        assert synthesis_complete(state) == "complete"

    def test_max_retries_exceeded(self):
        state = {
            "report": None,
            "error": "some error",
            "iteration": MAX_ITERATIONS,
        }
        assert synthesis_complete(state) == "max_retries_exceeded"

    def test_retry_when_below_max_with_error(self):
        state = {"report": None, "error": "some error", "iteration": 1}
        assert synthesis_complete(state) == "retry"

    def test_retry_when_empty_report_below_max(self):
        state = {"report": "", "error": "some error", "iteration": 1}
        assert synthesis_complete(state) == "retry"

    def test_retry_when_no_report_no_error(self):
        state = {"report": None, "error": None, "iteration": 1}
        assert synthesis_complete(state) == "retry"


class TestSynthesisGraphIntegration:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        llm = FakeSynthesisLLM(responses=["Final synthesized report"])
        with (
            patch("app.core.agents.synthesis.get_llm_provider", return_value=llm),
            patch("app.core.agents.synthesis.get_prompt", return_value=FakePrompt()),
        ):
            graph = build_synthesis_graph()
            result = await graph.ainvoke({**BASE_STATE})

        assert result.get("error") is None
        assert result["report"] == "Final synthesized report"
        assert result["iteration"] == 1
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_and_recover(self):
        llm = FakeSynthesisLLM(responses=["", "Report after retry"])
        with (
            patch("app.core.agents.synthesis.get_llm_provider", return_value=llm),
            patch("app.core.agents.synthesis.get_prompt", return_value=FakePrompt()),
        ):
            graph = build_synthesis_graph()
            result = await graph.ainvoke({**BASE_STATE})

        assert result.get("error") is None
        assert result["report"] == "Report after retry"
        assert result["iteration"] == 2
        assert llm.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        llm = FakeSynthesisLLM(responses=["", "", ""])
        with (
            patch("app.core.agents.synthesis.get_llm_provider", return_value=llm),
            patch("app.core.agents.synthesis.get_prompt", return_value=FakePrompt()),
        ):
            graph = build_synthesis_graph()
            result = await graph.ainvoke({**BASE_STATE})

        assert result.get("error") is not None
        assert "No report was generated" in result["error"]
        assert result["iteration"] == MAX_ITERATIONS
        assert llm.call_count == MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_loops_through_retries_when_prior_error_in_state(self):
        state = {**BASE_STATE, "error": "pre-existing error"}

        graph = build_synthesis_graph()
        result = await graph.ainvoke(state)

        assert result.get("error") is not None
        assert result["iteration"] == MAX_ITERATIONS
