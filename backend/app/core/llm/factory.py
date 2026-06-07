from app.config import get_settings
from app.core.llm.base import LLMProvider
from app.core.llm.echo import EchoProvider
from app.core.llm.ollama import OllamaProvider

_providers: dict[str, type[LLMProvider]] = {
    "echo": EchoProvider,
    "ollama": OllamaProvider,
}


def register_provider(name: str, provider_cls: type[LLMProvider]) -> None:
    """Register a new LLM provider class under a given name."""
    _providers[name] = provider_cls


def get_llm_provider() -> LLMProvider:
    """Returns a the settings-specified LLM provider instance, or a default EchoProvider if not found."""
    settings = get_settings()
    cls = _providers.get(settings.llm_provider)
    if cls is None:
        return EchoProvider()
    return cls()


# Para mantener un singleton por provider (opcional pero recomendado)
def get_cached_provider() -> LLMProvider:
    """Returns a cached instance of the settings-specified LLM provider."""
    settings = get_settings()
    cache_key = f"llm_provider_{settings.llm_provider}"

    import threading

    if not hasattr(get_cached_provider, "_cache"):
        get_cached_provider._cache = {}
        get_cached_provider._lock = threading.Lock()

    with get_cached_provider._lock:
        if cache_key not in get_cached_provider._cache:
            get_cached_provider._cache[cache_key] = get_llm_provider()
        return get_cached_provider._cache[cache_key]
