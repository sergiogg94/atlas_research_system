from app.core.tools.base import BaseTool
from app.core.tools.web_search import WebSearchTool

_tools: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool) -> None:
    _tools[tool.name] = tool


def get_tool(name: str) -> BaseTool:
    tool = _tools.get(name)
    if tool is None:
        raise KeyError(f"Tool '{name}' not found. Available: {list(_tools.keys())}")
    return tool


def list_tools() -> dict[str, str]:
    return {name: tool.description for name, tool in _tools.items()}


# Initial tool registration
register_tool(WebSearchTool())
