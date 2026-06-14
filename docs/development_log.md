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

---

## Week 2: Planner Agent & LangGraph (In Progress)

### Summary
This week was constrained by limited availability due to workload at my primary job. Despite that, I completed through **Day 4** of the plan: LangGraph setup, the prompt system, the Planner Agent implementation with a StateGraph, and the `/api/v1/plan` endpoint. Days 5–7 (tests, Ollama real integration, and documentation) remain pending and will be carried forward.

### Key Deliverables
- **LangGraph integrated** — `langgraph>=0.4.0` added to dependencies, compiled `requirements.txt` and `uv.lock`
- **Prompt system** — Abstract `PromptTemplate` base class with `template`, `version`, and `description` properties; versioned planner prompts (`planner_system` v1.0.0, `planner_user` v1.0.0); `get_prompt()` registry for lookup-by-name
- **Planner Agent** — LangGraph `StateGraph` with 3 nodes (`validate_task` → `generate_plan` → `parse_plan`), conditional edges for error routing, and full async support
- **Planner schemas** — `Plan`, `PlanStep`, `StepType` enum (scoping/research/analysis/synthesis), `PlanRequest`, `PlanResponse`; `BaseResponse` base class for all API responses
- **`POST /api/v1/plan` endpoint** — Invokes the compiled graph, validates input, returns structured plans with error propagation as HTTP 400

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| PromptTemplate as ABC | Enforces consistent versioning and metadata across all prompts; makes prompt iteration traceable |
| StepType enum | Categorizes each research step by purpose, enabling downstream agents to decide how to execute based on step type |
| Conditional error edges in LangGraph | Errors propagate through the graph explicitly rather than raising exceptions — keeps state consistent and debuggable |
| StateGraph over linear chain | The conditional routing foundation prepares for complex multi-agent orchestration in later weeks |
| BaseResponse for all endpoints | Consistent API response envelope (`status`, `timestamp`) from day one; avoids retrofitting later |

### Pending (carried to Week 3)
- [ ] Tests for LLM provider, Planner Agent, and `/plan` endpoint
- [ ] Retry logic with exponential backoff in LLM provider
- [ ] Timeout handling in `/plan` endpoint
- [ ] Real Ollama integration test
- [ ] Logging instrumentation in agent nodes
- [ ] Documentation updates (README, ARCHITECTURE)

### Key Learnings
1. **LangGraph state model** — The `TypedDict`-based state that LangGraph merges across nodes is elegant but requires discipline: every node must return the full state shape. Unlike Redux, there is no built-in reducer — you merge manually.
2. **Conditional edges as control flow** — `add_conditional_edges` with routing functions is the LangGraph equivalent of if/else. This pattern is essential for agents that make decisions (retry, skip, escalate).
3. **Async graph execution** — Mixing sync and async nodes in LangGraph works, but consistency matters. Making `validate_task` and `parse_plan` sync while `generate_plan` is async is intentional (I/O-bound vs CPU-bound separation).
4. **Prompt versioning as code** — Treating prompts as first-class classes with explicit versions makes it possible to A/B test, roll back, and audit prompt changes. This is a lightweight alternative to dedicated prompt management tools.
5. **Realistic scheduling** — With a full-time job, 2–3 hours daily is optimistic. Completing 4/7 days is a realistic pace; the key is shipping something functional each week.