from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generates an answer to the prompt."""
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Lists the available models."""
        ...
