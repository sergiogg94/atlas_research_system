from ddgs import DDGS

from app.core.logging import logger
from app.core.tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for current information. Use this to find recent data, news, or facts"

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        try:
            with DDGS() as ddgs:
                logger.info(
                    "Performing web search for query: '%s' with max_results=%s",
                    query,
                    max_results,
                )
                results = list(ddgs.text(query, max_results=max_results))
            return ToolResult(success=True, data=results)
        except Exception as e:
            logger.error("Error during web search for query '%s': %s", query, str(e))
            return ToolResult(success=False, error=str(e))

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }
