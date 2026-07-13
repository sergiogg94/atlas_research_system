import asyncio
import json
from datetime import datetime
from uuid import uuid4

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


class TestHistory:
    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client):
        mock_repo = AsyncMock()
        mock_repo.list_executions.return_value = ([], 0)

        with patch("app.api.routes.history.execution_repository", mock_repo):
            response = await client.get("/api/v1/tasks")

        assert response.status_code == 200
        data = response.json()
        assert data["executions"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, client):
        now = datetime.now()
        mock_exec = MagicMock()
        mock_exec.id = uuid4()
        mock_exec.trace_id = "trace-1"
        mock_exec.task_description = "Test task"
        mock_exec.objective = "obj"
        mock_exec.status = "completed"
        mock_exec.total_steps = 3
        mock_exec.error = None
        mock_exec.started_at = None
        mock_exec.completed_at = None
        mock_exec.created_at = now
        mock_exec.updated_at = now

        mock_repo = AsyncMock()
        mock_repo.list_executions.return_value = ([mock_exec], 1)

        with patch("app.api.routes.history.execution_repository", mock_repo):
            response = await client.get(
                "/api/v1/tasks?page=1&page_size=10&status=completed"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["executions"]) == 1
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["executions"][0]["trace_id"] == "trace-1"

    @pytest.mark.asyncio
    async def test_get_task_by_trace_id_200(self, client):
        now = datetime.now()
        exec_id = uuid4()
        mock_exec = MagicMock()
        mock_exec.id = exec_id
        mock_exec.trace_id = "trace-1"
        mock_exec.task_description = "Test task"
        mock_exec.objective = "obj"
        mock_exec.status = "completed"
        mock_exec.total_steps = 3
        mock_exec.error = None
        mock_exec.report = "Final report"
        mock_exec.started_at = None
        mock_exec.completed_at = None
        mock_exec.created_at = now
        mock_exec.updated_at = now

        mock_repo = AsyncMock()
        mock_repo.get_execution_by_trace_id.return_value = mock_exec
        mock_repo.get_steps.return_value = []
        mock_repo.get_llm_calls.return_value = []
        mock_repo.get_tool_calls.return_value = []

        with patch("app.api.routes.history.execution_repository", mock_repo):
            response = await client.get("/api/v1/tasks/trace-1")

        assert response.status_code == 200
        data = response.json()
        assert data["execution"]["trace_id"] == "trace-1"
        assert data["execution"]["status"] == "completed"
        assert data["execution"]["steps"] == []
        assert data["execution"]["llm_calls"] == []
        assert data["execution"]["tool_calls"] == []

    @pytest.mark.asyncio
    async def test_get_task_by_trace_id_404(self, client):
        mock_repo = AsyncMock()
        mock_repo.get_execution_by_trace_id.return_value = None

        with patch("app.api.routes.history.execution_repository", mock_repo):
            response = await client.get("/api/v1/tasks/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_task_metrics_200(self, client):
        exec_id = uuid4()
        mock_metrics = MagicMock()
        mock_metrics.execution_id = exec_id
        mock_metrics.trace_id = "trace-1"
        mock_metrics.total_duration_ms = 1500
        mock_metrics.total_llm_calls = 10
        mock_metrics.total_tool_calls = 5
        mock_metrics.total_steps = 3
        mock_metrics.total_tokens_input = 5000
        mock_metrics.total_tokens_output = 2000
        mock_metrics.estimated_cost_usd = 0.05
        mock_metrics.avg_step_latency_ms = 500.0
        mock_metrics.avg_llm_latency_ms = 150.0
        mock_metrics.error_count = 0

        mock_repo = AsyncMock()
        mock_repo.get_metrics.return_value = mock_metrics

        with patch("app.api.routes.history.execution_repository", mock_repo):
            response = await client.get("/api/v1/tasks/trace-1/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["trace_id"] == "trace-1"
        assert data["metrics"]["total_llm_calls"] == 10
        assert data["metrics"]["total_tool_calls"] == 5
        assert data["metrics"]["estimated_cost_usd"] == 0.05

    @pytest.mark.asyncio
    async def test_get_task_metrics_404(self, client):
        mock_repo = AsyncMock()
        mock_repo.get_metrics.return_value = None

        with patch("app.api.routes.history.execution_repository", mock_repo):
            response = await client.get("/api/v1/tasks/nonexistent/metrics")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
