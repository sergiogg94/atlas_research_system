from app.core.llm.base import LLMProvider


class EchoProvider(LLMProvider):
    async def generate(self, prompt: str, system: str | None = None) -> str:
        prefix = "[Echo] "
        if system:
            prefix = f"[Echo - system: {system[:30]}...] "
        return f"{prefix}Received: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"

    async def list_models(self) -> list[str]:
        return ["echo"]
