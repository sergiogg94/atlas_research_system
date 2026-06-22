import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.tools import get_tool, list_tools, register_tool
from app.core.tools.base import BaseTool, ToolResult
from app.core.tools.web_scraper import WebScraperTool
from app.core.tools.web_search import WebSearchTool


class TestWebSearchTool:
    @pytest.fixture
    def tool(self):
        return WebSearchTool()

    @pytest.mark.asyncio
    async def test_search_success(self, tool):
        fake_results = [
            {"title": "Result 1", "href": "https://example.com/1", "body": "Content"},
            {"title": "Result 2", "href": "https://example.com/2", "body": "Content"},
        ]
        mock_instance = MagicMock()
        mock_instance.text.return_value = fake_results

        with patch("app.core.tools.web_search.DDGS") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_instance
            result = await tool.execute(query="AI in healthcare")

        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0]["title"] == "Result 1"

    @pytest.mark.asyncio
    async def test_search_no_results(self, tool):
        mock_instance = MagicMock()
        mock_instance.text.return_value = []

        with patch("app.core.tools.web_search.DDGS") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_instance
            result = await tool.execute(query="nothing relevant")

        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_search_error(self, tool):
        mock_instance = MagicMock()
        mock_instance.text.side_effect = Exception("API rate limit exceeded")

        with patch("app.core.tools.web_search.DDGS") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_instance
            result = await tool.execute(query="test")

        assert result.success is False
        assert "API rate limit exceeded" in result.error

    @pytest.mark.asyncio
    async def test_search_custom_max_results(self, tool):
        mock_instance = MagicMock()
        mock_instance.text.return_value = []

        with patch("app.core.tools.web_search.DDGS") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_instance
            await tool.execute(query="test query", max_results=3)

        mock_instance.text.assert_called_once_with("test query", max_results=3)

    @pytest.mark.asyncio
    async def test_name_and_description(self, tool):
        assert tool.name == "web_search"
        assert tool.description


class TestWebScraperTool:
    @pytest.fixture
    def tool(self):
        return WebScraperTool()

    @pytest.mark.asyncio
    async def test_scrape_success(self, tool):
        html = "<html><body><p>Hello world</p></body></html>"
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            result = await tool.execute(url="https://example.com")

        assert result.success is True
        assert "Hello world" in result.data["content"]
        assert result.data["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_scrape_strips_non_content_tags(self, tool):
        html = """
        <html>
        <body>
            <script>alert('bad')</script>
            <style>.hidden{}</style>
            <nav>Sidebar nav</nav>
            <footer>Footer info</footer>
            <p>Main content here</p>
        </body>
        </html>
        """
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            result = await tool.execute(url="https://example.com")

        assert result.success is True
        assert "Main content here" in result.data["content"]
        assert "alert('bad')" not in result.data["content"]
        assert "Sidebar nav" not in result.data["content"]

    @pytest.mark.asyncio
    async def test_scrape_truncates_content(self, tool):
        long_text = "word " * 5000
        html = f"<html><body><p>{long_text}</p></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            result = await tool.execute(url="https://example.com", max_chars=100)

        assert result.success is True
        assert "[Content truncated...]" in result.data["content"]
        assert len(result.data["content"]) < len(long_text)

    @pytest.mark.asyncio
    async def test_scrape_timeout(self, tool):
        with patch(
            "httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")
        ):
            result = await tool.execute(url="https://example.com")

        assert result.success is False
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_scrape_http_error(self, tool):
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(spec=httpx.Request),
            response=response,
        )

        with patch("httpx.AsyncClient.get", return_value=response):
            result = await tool.execute(url="https://example.com/not-found")

        assert result.success is False
        assert "HTTP 404" in result.error

    @pytest.mark.asyncio
    async def test_scrape_generic_exception(self, tool):
        with patch(
            "httpx.AsyncClient.get",
            side_effect=RuntimeError("connection reset by peer"),
        ):
            result = await tool.execute(url="https://example.com")

        assert result.success is False
        assert "connection reset by peer" in result.error

    @pytest.mark.asyncio
    async def test_name_and_description(self, tool):
        assert tool.name == "web_scraper"
        assert tool.description


class TestToolRegistry:
    def test_get_tool_returns_registered_tool(self):
        tool = get_tool("web_search")
        assert isinstance(tool, WebSearchTool)

        tool = get_tool("web_scraper")
        assert isinstance(tool, WebScraperTool)

    def test_get_tool_raises_key_error_for_unknown(self):
        with pytest.raises(KeyError, match="unknown_tool"):
            get_tool("unknown_tool")

    def test_list_tools_returns_all_tools(self):
        tools = list_tools()
        assert "web_search" in tools
        assert "web_scraper" in tools
        assert len(tools) >= 2

    def test_register_tool_adds_and_overrides(self):
        from app.core.tools import _tools

        class MockTool(BaseTool):
            @property
            def name(self):
                return "mock_tool"

            @property
            def description(self):
                return "A mock tool for testing"

            async def execute(self, **kwargs):
                return ToolResult(success=True)

            def input_schema(self):
                return {}

        original = dict(_tools)
        try:
            register_tool(MockTool())
            assert get_tool("mock_tool") is not None
        finally:
            _tools.clear()
            _tools.update(original)
