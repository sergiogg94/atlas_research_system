import asyncio
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.llm.base import LLMProvider
from app.core.tools.base import ToolResult


class FakeLLMProvider(LLMProvider):
    def __init__(self, response="Mock response"):
        self._response = response

    async def generate(self, prompt: str, system: str | None = None) -> str:
        return self._response

    async def list_models(self) -> list[str]:
        return ["fake-model"]


PLAN_JSON = json.dumps({
    "objective": "Research the impact of AI on healthcare",
    "assumptions": ["AI adoption varies by region"],
    "steps": [
        {
            "step": 1,
            "action": "Define scope of AI in healthcare",
            "expected_output": "Scope definition document",
            "step_type": "scoping",
        },
    ],
})


class TestRoot:
    @pytest.mark.asyncio
    async def test_root_returns_message(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestHealth:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.ping = AsyncMock()
        r.close = AsyncMock()
        return r

    @pytest.fixture
    def mock_db(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()
        return conn

    @pytest.mark.asyncio
    async def test_health_all_healthy(self, client, mock_redis, mock_db):
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_db

        with (
            patch("redis.asyncio.from_url", return_value=mock_redis),
            patch("app.api.routes.health.engine", mock_engine),
        ):
            response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["redis"] == "healthy"
        assert data["services"]["database"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_redis_down(self, client, mock_redis, mock_db):
        mock_redis.ping.side_effect = Exception("Redis connection refused")
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_db

        with (
            patch("redis.asyncio.from_url", return_value=mock_redis),
            patch("app.api.routes.health.engine", mock_engine),
        ):
            response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["redis"] == "unhealthy"
        assert data["services"]["database"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_db_down(self, client, mock_redis, mock_db):
        mock_db.execute.side_effect = Exception("Database connection failed")
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_db

        with (
            patch("redis.asyncio.from_url", return_value=mock_redis),
            patch("app.api.routes.health.engine", mock_engine),
        ):
            response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["redis"] == "healthy"
        assert data["services"]["database"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_both_down(self, client, mock_redis, mock_db):
        mock_redis.ping.side_effect = Exception("Redis connection refused")
        mock_db.execute.side_effect = Exception("Database connection failed")
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_db

        with (
            patch("redis.asyncio.from_url", return_value=mock_redis),
            patch("app.api.routes.health.engine", mock_engine),
        ):
            response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["redis"] == "unhealthy"
        assert data["services"]["database"] == "unhealthy"


class TestGenerate:
    @pytest.mark.asyncio
    async def test_generate_success(self, client):
        provider = FakeLLMProvider(response="Hello from mock")

        with patch("app.api.routes.llm.get_llm_provider", return_value=provider):
            response = await client.post(
                "/api/v1/test/generate",
                json={"prompt": "Say hello"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["response"] == "Hello from mock"
        assert data["provider"] == "FakeLLMProvider"

    @pytest.mark.asyncio
    async def test_generate_timeout(self, client):
        provider = AsyncMock(spec=LLMProvider)
        provider.generate.side_effect = asyncio.TimeoutError()

        with patch("app.api.routes.llm.get_llm_provider", return_value=provider):
            response = await client.post(
                "/api/v1/test/generate",
                json={"prompt": "Say hello"},
            )

        assert response.status_code == 504


class TestListModels:
    @pytest.mark.asyncio
    async def test_list_models_success(self, client):
        provider = FakeLLMProvider()

        with patch("app.api.routes.llm.get_llm_provider", return_value=provider):
            response = await client.get("/api/v1/test/models")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "fake-model" in data["models"]

    @pytest.mark.asyncio
    async def test_list_models_timeout(self, client):
        provider = AsyncMock(spec=LLMProvider)
        provider.list_models.side_effect = asyncio.TimeoutError()

        with patch("app.api.routes.llm.get_llm_provider", return_value=provider):
            response = await client.get("/api/v1/test/models")

        assert response.status_code == 504


class TestPlan:
    @pytest.mark.asyncio
    async def test_create_plan_success(self, client):
        provider = FakeLLMProvider(response=PLAN_JSON)

        with patch(
            "app.core.agents.planner.get_llm_provider", return_value=provider
        ):
            response = await client.post(
                "/api/v1/plan",
                json={"task_description": "Research the impact of AI on healthcare"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["plan"]["objective"]
        assert len(data["plan"]["steps"]) >= 1

    @pytest.mark.asyncio
    async def test_create_plan_invalid_request(self, client):
        response = await client.post(
            "/api/v1/plan",
            json={"task_description": "Hi"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_plan_llm_error(self, client):
        provider = FakeLLMProvider(response="not valid json")

        with patch(
            "app.core.agents.planner.get_llm_provider", return_value=provider
        ):
            response = await client.post(
                "/api/v1/plan",
                json={"task_description": "Research the impact of AI on healthcare"},
            )

        assert response.status_code == 400


class TestResearch:
    @pytest.mark.asyncio
    async def test_research_success(self, client):
        provider = FakeLLMProvider(
            response="AI is transforming healthcare through diagnostics."
        )
        search_tool = AsyncMock()
        search_tool.execute.return_value = ToolResult(
            success=True,
            data=[
                {
                    "title": "AI in Healthcare",
                    "href": "https://example.com/ai",
                    "body": "Content",
                }
            ],
        )
        scraper_tool = AsyncMock()
        scraper_tool.execute.return_value = ToolResult(
            success=True,
            data={
                "url": "https://example.com/ai",
                "content": "Detailed AI content",
                "word_count": 3,
            },
        )

        def get_tool_side_effect(name):
            if name == "web_search":
                return search_tool
            if name == "web_scraper":
                return scraper_tool
            raise KeyError(name)

        with (
            patch(
                "app.core.agents.research.get_llm_provider", return_value=provider
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            response = await client.post(
                "/api/v1/research",
                json={
                    "objective": "Research the impact of AI on healthcare",
                    "steps": [
                        {
                            "action": "Analyze current AI adoption",
                            "expected_output": "Analysis report",
                            "step_type": "research",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["findings"]) >= 1
        assert data["total_steps"] >= 1

    @pytest.mark.asyncio
    async def test_research_invalid_request(self, client):
        response = await client.post(
            "/api/v1/research",
            json={
                "objective": "Hi",
                "steps": [{"action": "test"}],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_research_search_failure(self, client):
        provider = FakeLLMProvider()
        search_tool = AsyncMock()
        search_tool.execute.return_value = ToolResult(
            success=False, error="Search API error"
        )
        scraper_tool = AsyncMock()

        def get_tool_side_effect(name):
            if name == "web_search":
                return search_tool
            if name == "web_scraper":
                return scraper_tool
            raise KeyError(name)

        with (
            patch(
                "app.core.agents.research.get_llm_provider", return_value=provider
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            response = await client.post(
                "/api/v1/research",
                json={
                    "objective": "Research the impact of AI on healthcare",
                    "steps": [
                        {
                            "action": "Analyze current AI adoption",
                            "expected_output": "Analysis report",
                            "step_type": "research",
                        }
                    ],
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_research_scraper_failure_continues(self, client):
        provider = FakeLLMProvider(
            response="AI is transforming healthcare through diagnostics."
        )
        search_tool = AsyncMock()
        search_tool.execute.return_value = ToolResult(
            success=True,
            data=[
                {
                    "title": "AI in Healthcare",
                    "href": "https://example.com/ai",
                    "body": "Content",
                }
            ],
        )
        scraper_tool = AsyncMock()
        scraper_tool.execute.return_value = ToolResult(
            success=False, error="Timeout scraping URL"
        )

        def get_tool_side_effect(name):
            if name == "web_search":
                return search_tool
            if name == "web_scraper":
                return scraper_tool
            raise KeyError(name)

        with (
            patch(
                "app.core.agents.research.get_llm_provider", return_value=provider
            ),
            patch(
                "app.core.agents.research.get_tool",
                side_effect=get_tool_side_effect,
            ),
        ):
            response = await client.post(
                "/api/v1/research",
                json={
                    "objective": "Research the impact of AI on healthcare",
                    "steps": [
                        {
                            "action": "Analyze current AI adoption",
                            "expected_output": "Analysis report",
                            "step_type": "research",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["findings"]) >= 1
