import pytest
from unittest.mock import AsyncMock, patch

from app.core.agents.research import build_research_graph
from app.core.llm.base import LLMProvider
from app.core.tools.base import ToolResult


class FakeLLMProvider(LLMProvider):
    async def generate(self, prompt: str, system: str | None = None) -> str:
        return (
            "AI is transforming healthcare through improved diagnostics "
            "and personalized medicine."
        )

    async def list_models(self) -> list[str]:
        return ["fake"]


SEARCH_RESULTS = [
    {
        "title": "AI in Healthcare 2024",
        "href": "https://example.com/1",
        "body": "Content about AI diagnostics",
    },
]

SCRAPED_DATA = {
    "url": "https://example.com/1",
    "content": "AI is transforming healthcare through diagnostics.",
    "word_count": 8,
}


def build_mock_tools(search_result=SEARCH_RESULTS, scraper_result=SCRAPED_DATA):
    search_tool = AsyncMock()
    search_tool.execute.return_value = ToolResult(
        success=True, data=search_result
    )
    search_tool.name = "web_search"

    scraper_tool = AsyncMock()
    scraper_tool.execute.return_value = ToolResult(
        success=True, data=scraper_result
    )
    scraper_tool.name = "web_scraper"

    def side_effect(name):
        if name == "web_search":
            return search_tool
        if name == "web_scraper":
            return scraper_tool
        raise KeyError(name)

    return search_tool, scraper_tool, side_effect


def build_initial_state(steps, **overrides):
    defaults = {
        "objective": "Research the impact of AI on healthcare",
        "steps": steps,
        "current_step": 0,
        "findings": [],
        "error": None,
        "current_query": None,
        "search_results": None,
        "scraped_contents": None,
    }
    defaults.update(overrides)
    return defaults


SINGLE_STEP = [
    {
        "action": "Analyze current AI adoption in clinical settings",
        "expected_output": "Analysis report",
        "step_type": "research",
    },
]

TWO_STEPS = [
    {
        "action": "Analyze current AI adoption in clinical settings",
        "expected_output": "Analysis report",
        "step_type": "research",
    },
    {
        "action": "Evaluate regulatory landscape for AI in healthcare",
        "expected_output": "Regulatory overview",
        "step_type": "analysis",
    },
]


class TestResearchAgent:
    @pytest.mark.asyncio
    async def test_single_step_completes_successfully(self):
        _, _, get_tool_side_effect = build_mock_tools()

        with (
            patch(
                "app.core.agents.research.get_llm_provider",
                return_value=FakeLLMProvider(),
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            graph = build_research_graph()
            result = await graph.ainvoke(
                build_initial_state(SINGLE_STEP)
            )

        assert result.get("error") is None
        assert len(result.get("findings", [])) == 1
        assert result["current_step"] == 1
        assert result["findings"][0]["step"] == 0

    @pytest.mark.asyncio
    async def test_multiple_steps_loop(self):
        _, _, get_tool_side_effect = build_mock_tools()

        with (
            patch(
                "app.core.agents.research.get_llm_provider",
                return_value=FakeLLMProvider(),
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            graph = build_research_graph()
            result = await graph.ainvoke(
                build_initial_state(TWO_STEPS)
            )

        assert result.get("error") is None
        assert len(result.get("findings", [])) == 2
        assert result["current_step"] == 2
        assert result["findings"][0]["step"] == 0
        assert result["findings"][1]["step"] == 1

    @pytest.mark.asyncio
    async def test_search_failure_sets_error(self):
        search_tool, _, get_tool_side_effect = build_mock_tools()
        search_tool.execute.return_value = ToolResult(
            success=False, error="DuckDuckGo rate limited"
        )

        with (
            patch(
                "app.core.agents.research.get_llm_provider",
                return_value=FakeLLMProvider(),
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            graph = build_research_graph()
            result = await graph.ainvoke(
                build_initial_state(SINGLE_STEP)
            )

        assert result.get("error") is not None
        assert "DuckDuckGo rate limited" in result["error"]

    @pytest.mark.asyncio
    async def test_scraper_failure_continues_with_empty_contents(self):
        search_tool, scraper_tool, get_tool_side_effect = build_mock_tools()
        scraper_tool.execute.return_value = ToolResult(
            success=False, error="Timeout scraping URL"
        )

        with (
            patch(
                "app.core.agents.research.get_llm_provider",
                return_value=FakeLLMProvider(),
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            graph = build_research_graph()
            result = await graph.ainvoke(
                build_initial_state(SINGLE_STEP)
            )

        assert result.get("error") is None
        assert result.get("scraped_contents") == []
        assert len(result.get("findings", [])) == 1

    @pytest.mark.asyncio
    async def test_no_search_results_skips_scraper(self):
        search_tool, _, get_tool_side_effect = build_mock_tools(
            search_result=[]
        )

        with (
            patch(
                "app.core.agents.research.get_llm_provider",
                return_value=FakeLLMProvider(),
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            graph = build_research_graph()
            result = await graph.ainvoke(
                build_initial_state(SINGLE_STEP)
            )

        assert result.get("error") is None
        assert result.get("search_results") == []
        # scrape_content skipped when no search_results
        assert result.get("scraped_contents") is None
        assert len(result.get("findings", [])) == 1

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_summary(self):
        class BrokenLLM(LLMProvider):
            async def generate(self, prompt: str, system: str | None = None) -> str:
                return ""

            async def list_models(self) -> list[str]:
                return ["broken"]

        _, _, get_tool_side_effect = build_mock_tools()

        with (
            patch(
                "app.core.agents.research.get_llm_provider",
                return_value=BrokenLLM(),
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            graph = build_research_graph()
            result = await graph.ainvoke(
                build_initial_state(SINGLE_STEP)
            )

        assert result.get("error") is None
        assert len(result.get("findings", [])) == 1
        summary = result["findings"][0]["summary"]
        assert summary == "No summary could be generated."
