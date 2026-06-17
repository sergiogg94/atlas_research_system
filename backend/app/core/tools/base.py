from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unic name for the tool"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the tool to be used by the llm when deciding which tool to call."""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given parameters."""
        ...

    @abstractmethod
    def input_schema(self) -> dict:
        """JSON schema for the input parameters of the tool."""
        ...
