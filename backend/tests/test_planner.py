import json

import pytest
from unittest.mock import patch

from app.core.agents.planner import build_planner_graph
from app.core.llm.base import LLMProvider

FAKE_PLAN = {
    "objective": "Research the impact of AI on healthcare",
    "assumptions": ["AI adoption varies by region"],
    "steps": [
        {
            "step": 1,
            "action": "Define scope of AI in healthcare",
            "expected_output": "Scope definition document",
            "step_type": "scoping",
        },
        {
            "step": 2,
            "action": "Gather recent data on AI adoption",
            "expected_output": "Data collection report",
            "step_type": "research",
        },
        {
            "step": 3,
            "action": "Analyze benefits and risks",
            "expected_output": "Analysis report",
            "step_type": "analysis",
        },
    ],
}


class FakeLLMProvider(LLMProvider):
    async def generate(self, prompt: str, system: str | None = None) -> str:
        return json.dumps(FAKE_PLAN)

    async def list_models(self) -> list[str]:
        return ["fake"]


@pytest.mark.asyncio
async def test_planner_rejects_short_task():
    graph = build_planner_graph()
    result = await graph.ainvoke({"task_description": "Hi"})
    assert result.get("error") is not None


@pytest.mark.asyncio
async def test_planner_generates_valid_plan():
    with patch(
        "app.core.agents.planner.get_llm_provider", return_value=FakeLLMProvider()
    ):
        graph = build_planner_graph()
        result = await graph.ainvoke(
            {
                "task_description": "Research the impact of AI on healthcare",
            }
        )
        assert result.get("plan") is not None
        assert len(result["plan"].steps) >= 1
        assert result["plan"].objective


@pytest.mark.asyncio
async def test_planner_handles_invalid_json():
    class BrokenProvider(LLMProvider):
        async def generate(self, prompt: str, system: str | None = None) -> str:
            return "this is not json"

        async def list_models(self) -> list[str]:
            return ["broken"]

    with patch(
        "app.core.agents.planner.get_llm_provider", return_value=BrokenProvider()
    ):
        graph = build_planner_graph()
        result = await graph.ainvoke(
            {"task_description": "Research AI in healthcare"}
        )
        assert result.get("error") is not None
        assert "parse" in result["error"].lower()


@pytest.mark.asyncio
async def test_planner_handles_validation_error():
    class BadPlanProvider(LLMProvider):
        async def generate(self, prompt: str, system: str | None = None) -> str:
            return json.dumps({
                "objective": "A plan",
                "assumptions": [],
                "steps": [
                    {
                        "step": 1,
                        "action": "Do something",
                        "expected_output": "Result",
                        "step_type": "invalid_type",
                    }
                ],
            })

        async def list_models(self) -> list[str]:
            return ["bad"]

    with patch(
        "app.core.agents.planner.get_llm_provider", return_value=BadPlanProvider()
    ):
        graph = build_planner_graph()
        result = await graph.ainvoke(
            {"task_description": "Research AI in healthcare"}
        )
        assert result.get("error") is not None


@pytest.mark.asyncio
async def test_planner_handles_empty_response():
    class EmptyProvider(LLMProvider):
        async def generate(self, prompt: str, system: str | None = None) -> str:
            return ""

        async def list_models(self) -> list[str]:
            return ["empty"]

    with patch(
        "app.core.agents.planner.get_llm_provider", return_value=EmptyProvider()
    ):
        graph = build_planner_graph()
        result = await graph.ainvoke(
            {"task_description": "Research AI in healthcare"}
        )
        assert result.get("error") is not None


@pytest.mark.asyncio
async def test_planner_accepts_valid_ten_char_task():
    task = "x" * 10
    graph = build_planner_graph()
    with patch(
        "app.core.agents.planner.get_llm_provider", return_value=FakeLLMProvider()
    ):
        result = await graph.ainvoke({"task_description": task})
        assert result.get("error") is None
        assert result.get("plan") is not None
