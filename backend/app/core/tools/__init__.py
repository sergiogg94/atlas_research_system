from app.core.tools.base import BaseTool
from app.core.tools.python_executor import PythonExecutorTool
from app.core.tools.web_scraper import WebScraperTool
from app.core.tools.web_search import WebSearchTool
from app.core.tools.sql_query import SQLQueryTool
from app.core.tracing import wrap_tool

_tools: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool) -> None:
    _tools[tool.name] = tool


def get_tool(name: str) -> BaseTool:
    tool = _tools.get(name)
    if tool is None:
        raise KeyError(f"Tool '{name}' not found. Available: {list(_tools.keys())}")
    return wrap_tool(tool)


def list_tools() -> dict[str, str]:
    return {name: tool.description for name, tool in _tools.items()}


# Initial tool registration
register_tool(WebSearchTool())
register_tool(WebScraperTool())
register_tool(PythonExecutorTool())
register_tool(SQLQueryTool())
