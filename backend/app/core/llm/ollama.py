import httpx
from tenacity import retry

from app.config import get_settings
from app.core.llm.base import LLMProvider
from app.core.llm.retry import retry_config
from app.core.logging import logger


class OllamaProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url or "http://localhost:11434"
        self.model = settings.ollama_model
        logger.info(
            "OllamaProvider configured: base_url=%s model=%s",
            self.base_url,
            self.model,
        )

    @retry(**retry_config)
    async def generate(self, prompt: str, system: str | None = None) -> str:
        logger.info("Ollama generate request: base_url=%s model=%s", self.base_url, self.model)
        logger.debug("Ollama prompt length: %s", len(prompt) if prompt else 0)
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }

            if system:
                payload["system"] = system

            response = await client.post(f"{self.base_url}/api/generate", json=payload)

            response.raise_for_status()
            data = response.json()
            result = data.get("response", "")

            logger.info("Ollama generate successful; response_length=%s", len(result))
            logger.debug("Ollama response preview: %s", (result or "")[:500])

            return result

    @retry(**retry_config)
    async def list_models(self) -> list[str]:
        logger.info("Listing Ollama models from %s", self.base_url)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            logger.info("Ollama returned %s models", len(models))
            return models
