# Development Log

## Week 1: Infrastructure & LLM Abstraction Layer

### Summary
Laid the foundation for a production-grade multi-agent research system. Built the complete backend infrastructure with FastAPI, Docker Compose, PostgreSQL, and Redis, plus an abstract LLM provider layer that supports multiple backends (Echo for testing, Ollama for real inference).

### Key Deliverables
- **Docker Compose** with 3 services (backend, PostgreSQL 15, Redis 7) orchestrated together
- **FastAPI backend** with health check, LLM test endpoints, CORS middleware, and Swagger docs
- **PostgreSQL async setup** using SQLAlchemy 2.0 async engine + Task model with UUID PK
- **LLM abstraction layer** — abstract `LLMProvider` base class with `EchoProvider` (mock) and `OllamaProvider` (real), wired through a config-driven factory pattern
- **Structured logging** with `colorlog` for readable debug output
- **Pydantic v2 config** with centralized env-var management (`pydantic-settings`)
- **DB init script** ready for schema migrations

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| Abstract LLM Provider | Model-agnostic design; swap Ollama for OpenAI/Anthropic without touching agent code. Essential for production AI systems. |
| EchoProvider as default | Enables development, testing, and CI without a GPU. Prevents LLM-dependency lock-in from day one. |
| Factory + cached singleton | Thread-safe provider selection via config (`LLM_PROVIDER` env var). Extensible: register a new provider with one call. |
| Async everything | FastAPI + asyncpg + async SQLAlchemy — non-blocking I/O is critical for LLM latency tolerance. |
| Python 3.13 + uv | Modern toolchain; `uv` is measurably faster than pip for dependency resolution. |

### Key Learnings
1. **Provider abstraction patterns** — The Strategy pattern applied to LLMs makes the system testable and future-proof.
2. **Docker Compose networking** — Services communicate by container name, not localhost.
3. **Async SQLAlchemy 2.0** — The `async_sessionmaker` pattern is cleaner and aligns with modern Python async practices. Know the difference between `sync` and `async` ORM sessions.
4. **Pydantic v2 for config** — `pydantic-settings` with `.env` loading is the de facto standard for production FastAPI apps. Using `lru_cache` on `get_settings()` prevents repeated file I/O.
5. **Designing for testability** — The EchoProvider means every component can be integration-tested without a real LLM. This decoupling between infrastructure and business logic is a hallmark of production AI systems.