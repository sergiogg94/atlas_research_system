from typing import Optional

import httpx
from app.config import get_settings
from app.core.llm.base import LLMProvider
from app.core.llm.retry import retry_config
from tenacity import retry


class OllamaProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url or "http://localhost:11434"
        self.model = settings.ollama_model

    @retry(**retry_config)
    async def generate(self, prompt: str, system: Optional[str] = None) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }

            if system:
                payload["system"] = system

            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )

            response.raise_for_status()

            return response.json()["response"]

    @retry(**retry_config)
    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/tags")
            data = response.json()

            return [m["name"] for m in data.get("models", [])]
