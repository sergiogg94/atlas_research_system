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

---

## Week 3: Tools Layer, Research Agent & Redis State

### Summary
This week closed the pending items from the previous plan and implemented the `tools` layer together with the Research Agent end-to-end. Two practical tools were added (web search and scraper), an API to run research jobs (`POST /api/v1/research`), state persistence in Redis, and dedicated prompts for synthesizing findings. Support for automatic agent documentation (Mermaid script) was also added, and logging, retry, and timeout configurations were improved where needed.

### Key Deliverables
- **BaseTool**: abstract interface for tools (`app/core/tools/base.py`) and registration/discovery of tools (`app/core/tools/__init__.py`).
- **WebSearchTool**: DuckDuckGo-based search (`app/core/tools/web_search.py`), input schema and error handling.
- **WebScraperTool**: lightweight scraper using `httpx` + `BeautifulSoup` that cleans and truncates content (`app/core/tools/web_scraper.py`).
- **Tool registry**: automatic tool registration and initialization accessible from agents.
- **Research Agent**: LangGraph `StateGraph` with nodes `parse_step`, `search_web`, `scrape_content`, `synthesize_finding` and conditional control flow (`app/core/agents/research.py`).
- **Prompts**: `research_system` and `research_user` templates to guide LLM synthesis (`app/core/prompts/research.py`).
- **Endpoint `/api/v1/research`**: route that invokes the graph and returns a `ResearchResponse` with timeout and error handling (`backend/app/api/routes/research.py`).
- **Redis client & StateManager**: async Redis client and helpers to persist/retrieve research state (`app/core/redis_client.py`, `app/core/state_manager.py`).
- **Agent docs generator**: `backend/scripts/generate_agent_docs.py` which produces Mermaid diagrams from agent definitions.
- **Tests & infra**: partial tests added/adjusted, logging improvements, and retry configuration for the LLM provider.

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| Schema-driven tools | Each `Tool` exposes an `input_schema()` so prompts or an orchestrator can invoke it without bespoke code. This facilitates tool-calling and validation. |
| Central tool registry | Registration in `app.core.tools` allows discovery and reuse of tools from any agent without coupling implementations. |
| Research Agent as looped StateGraph | The graph repeats: parse → search → scrape → synthesize over plan steps, enabling retries, checkpoints, and incremental processing. |
| LLM synthesis separated by prompts | `system` and `user` templates keep synthesis responsibility isolated from agent code, easing prompt engineering iterations. |
| Redis for ephemeral checkpoints | Persisting partial state in Redis allows resuming long-running research and debugging progress without filling the main database. |

### Key Learnings
1. **Pragmatic tool-calling** — Designing `ToolResult` and `input_schema()` makes integrations with LLMs and agents much more robust; edges between nodes become clearer when tools return predictable shapes.
2. **Scraping trade-offs** — `httpx` + `BeautifulSoup` works for most articles, but dynamic pages or those requiring JS are out of scope; truncation and cleaning are required to control token usage.
3. **Search without API keys** — DuckDuckGo (DDGS) is sufficient for research prototyping and avoids key dependencies in early stages.
4. **Observability matters** — More detailed logging in nodes and tools makes failures reproducible; messages were added to indicate when a node is skipped due to an error.
5. **Timeouts and expectations** — The `/api/v1/research` endpoint uses a wide timeout (10 minutes) to allow multi-step pipelines; in production timeouts should be tuned and checkpoints/pagination used.

---

## Week 4: Data Agent, Python Executor & SQL Query Tool

### Summary
This week completed the core data-processing layer of the multi-agent system. Three major components were built: a sandboxed Python executor with AST-level security validation, a read-only SQL query tool against PostgreSQL, and a full Data Agent (LangGraph StateGraph) that uses an LLM to analyze tasks and generate/execute code or SQL. The testing infrastructure was also significantly expanded with comprehensive test suites for all tools, agents (Research and Data), and API endpoints.

### Key Deliverables
- **PythonExecutorTool** — Sandboxed Python execution via `subprocess` with AST validation, whitelist-based import control, empty environment, memory limits, CPU timeout, and code sanitization. Blocks `os`, `subprocess`, `exec`, `eval`, `compile`, `__import__`, `open` at the AST level.
- **SQLQueryTool** — PostgreSQL read-only query tool accepting `SELECT` and `WITH` CTE statements. Validation covers forbidden DDL/DML patterns (INSERT, UPDATE, DELETE, DROP, TRUNCATE, etc.), multi-statement detection, SQL comments, and dangerous PostgreSQL functions via regex.
- **Data Agent** — LangGraph `StateGraph` with 4 async nodes (`analyze_task` → `generate_code` → `execute_python`/`execute_sql`). Conditional edges route to Python or SQL based on LLM analysis, and a retry loop re-generates code up to 3 times on execution errors.
- **Data prompts** — 4 versioned prompt templates (`data_analysis_system`, `data_analysis_user`, `data_code_gen_system`, `data_code_gen_user`) registered in a centralized prompt registry.
- **Endpoint `POST /api/v1/data`** — Accepts `DataRequest` (task, context, max_iterations), runs the Data Agent graph with a 180s timeout, returns `DataResponse` with code/query/result/error.
- **Comprehensive test suite:**
  - `test_tools.py` — 35 tests covering all 4 tools (search, scraper, python executor security/functionality, SQL validation, tool registry)
  - `test_research.py` — 6 tests for the Research Agent (single/multi-step, search/scraper/LLM failure modes)
  - `test_data_agent.py` — 8 tests for the Data Agent (Python/SQL paths, retry logic, max retries, empty responses, error propagation)
  - `test_api.py` — 16 integration tests for all 5 endpoints (root, health, generate, models, plan, research) using `TestClient` and mocked providers
  - `conftest.py` — Test fixtures (async client, DB session, LLM provider)

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| AST-level import validation | Catches dangerous imports before execution without running the code; complements runtime sandboxing |
| Subprocess with empty `env={}` | Prevents access to environment variables, PATH, and system config from executed code |
| `resource.setrlimit` for memory/CPU | Linux-native resource limits are more robust than Python-level guards against infinite loops and memory bombs |
| Subprocess sandbox over Docker-in-Docker | Docker sandboxing was considered but subprocess + `resource` limits + AST validation was chosen for lower complexity, no container runtime dependency, and sufficient isolation for a prototyping phase. Docker sandbox remains the production target for true multi-tenant isolation |
| SQL validation via regex patterns | Covers 20+ forbidden patterns (DDL, DML, dangerous functions) with a single pass; easy to extend |
| Data Agent as conditional StateGraph | The LLM decides the execution path (Python vs SQL) rather than hardcoding it, making the agent flexible across data tasks |
| Retry loop in graph edges (max 3) | Self-healing: the LLM receives the previous error and generates corrected code, without human intervention |
| Centralized test infrastructure | `conftest.py` with `AsyncClient`, `FakeLLMProvider`, and mock tools enables fast, deterministic tests without external dependencies |

### Key Learnings
1. **AST-based security is layered, not absolute** — Parsing the AST blocks statically detectable dangerous patterns, but dynamic attacks (e.g., `getattr(__builtins__, 'exec')`) require runtime sandboxing. Combining AST validation + subprocess isolation + resource limits provides defense in depth.
2. **SQL validation is an arms race** — Regex-based blocking of dangerous patterns works for common cases but is not exhaustive. Prepared statements via `text()` + params mitigate injection risks, and restricting to SELECT/WITH limits the blast radius.
3. **Mocking LangGraph for tests** — Patching `get_llm_provider` and `get_tool` at the module level (where they are imported) lets tests run the full graph without a real LLM or external services. `FakeLLMProvider` with controllable responses enables precise path coverage.
4. **Conditional edges are the agent's decision logic** — The `needs_sql` and `has_error` routing functions in the Data Agent mirror real decision-making. Testing these functions in isolation (unit tests) before running the full graph catches routing bugs early.
5. **Prompt engineering for code generation** — The data code-gen prompts include the previous error message on retry, which significantly improves the LLM's ability to self-correct. Explicit safety rules in the system prompt reduce hallucinated dangerous code.

---

## Week 5: Synthesis Agent & Multi-Agent Orchestration

### Summary
Implemented the final piece of agent orchestration: the Synthesis Agent that consolidates findings from all upstream agents into structured reports, plus a master Orchestrator graph that connects Planner → Research → Data → Synthesis in a single pipeline. Added Redis checkpoints for state persistence across nodes, an LLM-driven re-planning mechanism that recovers from agent failures (retry/skip/abort), and safety limits (max steps, degradation detection) to prevent runaway execution. Exposed the full pipeline via `POST /api/v1/execute-task` with a 10-minute timeout.

### Key Deliverables
- **Synthesis Agent** — LangGraph `StateGraph` with 3 nodes (`collect_results` → `generate_synthesis` → `validate_report`), conditional retry loop (max 3 iterations), and versioned prompts (`synthesis_system` v1.0.0, `synthesis_user` v1.0.0)
- **Master Orchestrator** — `StateGraph` with 7 nodes: 4 agent nodes (`run_planner`, `run_research`, `run_data`, `run_synthesis`), 2 safety nodes (`check_max_steps`, `check_degradation`), and 1 recovery node (`re_plan`). Conditional routing via `route_from_planner/research/data` and `route_after_replan`
- **Redis checkpoints** — `save_checkpoint` with `_sanitize_for_json` helper and `with_checkpoint` decorator; state persisted after each agent node via `StateManager.save_orchestrator_state`
- **Re-planning** — LLM-based decision node (`re_plan`) that parses JSON `{"decision": "retry"|"skip"|"abort"}`; degradation detection aborts after 3 consecutive failures on the same agent
- **Data Agent context builder** — `_build_data_context` that assembles research findings and plan context for the Data Agent, with truncation at 5000 chars
- **Endpoint `POST /api/v1/execute-task`** — Accepts `ExecuteTaskRequest` (task_description: 10–2000 chars), runs full orchestrator graph with 600s `asyncio.wait_for`, returns `ExecuteTaskResponse` with objective, plan, research findings, data results, report, error, and total_steps
- **Orchestrator schemas** — `ExecuteTaskRequest`, `ExecuteTaskResponse` with `BaseResponse` envelope
- **Test suite** — 6 tests in `test_orchestrator.py` covering planner node, full mocked pipeline, data-agent skipping, LLM-based re-planning, max-steps enforcement, and checkpoint persistence
- **Documentation** — `docs/orchestrator_graph.md` with Mermaid diagram, state table, node descriptions, and edge matrix

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| Orchestrator as master StateGraph | Encapsulates the entire multi-agent pipeline in a single compiled graph; each agent is a node, enabling unified control flow, error handling, and state persistence |
| Two safety layers (max_steps + degradation) | `check_max_steps` prevents infinite loops (hard limit at 50); `check_degradation` detects cascading failures (soft limit at 3 consecutive) and aborts before wasting LLM calls |
| LLM-based re-planning over hardcoded fallback | The LLM decides whether to retry, skip, or abort based on error context — more flexible than static routing; JSON response parsed for reliability |
| Checkpoints after every agent node | Redis persistence via `save_checkpoint` enables debugging, recovery, and audit of long-running executions; the `_sanitize_for_json` step prevents serialization failures from non-JSON-safe state fields |
| `with_checkpoint` decorator | Applied transparently to agent nodes without modifying their internal logic; keeps checkpointing separate from business logic |
| Synthesis retry loop (max 3) | Self-healing: the LLM receives previous validation errors and regenerates the report. After 3 failed attempts, the graph terminates gracefully rather than looping forever |

### Key Learnings
1. **Orchestrator as composition over inheritance** — Each agent is a standalone `StateGraph`, and the orchestrator invokes them as sub-graphs. This keeps agents independently testable and the orchestrator focused on routing and safety.
2. **Checkpoint trade-offs** — Persisting state after every node adds latency (~5–10ms per Redis write) but provides valuable debugging and recovery capability. The `_sanitize_for_json` step is essential because LangGraph state can contain non-serializable objects (e.g., Pydantic models).
3. **LLM-based re-planning is powerful but fragile** — The LLM correctly decides retry/skip/abort in most cases, but malformed JSON responses require a try/except fallback. Adding few-shot examples to the prompt would improve reliability.
4. **Safety layers must be tested explicitly** — `test_max_steps_limit` and `test_replan_on_error` catch edge cases that would otherwise cause infinite loops or silent failures in production. These tests are cheap to write and invaluable for confidence.
5. **Graph compilation errors surface structural issues** — The orchestrator graph compilation (7 nodes, 9+ edges) revealed mismatches between routing function return values and edge destination names. Compilation-time validation in LangGraph catches these before runtime.

---

## Week 6: Observability, Execution Persistence & Data Agent Refinements

### Summary
Implemented a complete observability layer with end-to-end trace_id propagation, structured logging with context, and full execution history persistence in PostgreSQL (4 new tables). Added history query endpoints (list, detail, metrics), automatic LLM and tool call recording via transparent wrappers, and a `trace_step` decorator for latency tracking. Refined the Data Agent with a new `classify_output` node that splits generated code into Python/SQL/both using dedicated prompts. Documented the execution database schema with a Mermaid ER diagram.

### Key Deliverables
- **Trace ID infrastructure** — `TraceIDMiddleware` assigns/generates trace_id per request; `ContextVar`-based propagation (`trace_id_var`, `agent_name_var`, `execution_id_var`, `step_id_var`) across all agents and the orchestrator; `trace_context` contextmanager for node-level scoping
- **Structured logging with context** — `ContextFormatter` (extending `colorlog.ColoredFormatter`) injects `trace_id` and `agent_name` into every log record; log format updated to `[trace_id] [agent_name] (timestamp) (module func): message`
- **`trace_step` decorator** — Wraps agent nodes with automatic latency measurement and logging; attaches `last_step_latency_ms` to state
- **PostgreSQL execution schema** — 5 models: `Execution` (with `ExecutionStatus` enum: pending/running/completed/failed/timeout), `ExecutionStep`, `LLMCall`, `ToolCallRecord`, and `ExecutionMetricsCache` — all with proper FKs, indexes, and cascade rules
- **ExecutionRepository** — Full CRUD + query methods (`create_execution`, `update_execution`, `add_step`, `add_llm_call`, `add_tool_call`, `list_executions` with pagination, `get_steps`, `get_llm_calls`, `get_tool_calls`)
- **Orchestrator integration** — `run_planner` creates an `Execution` record on start; every agent node records an `ExecutionStep`; `run_synthesis` marks `COMPLETED`; checkpoints and re_plan/degradation nodes update status to `FAILED`/`TIMEOUT`
- **LLM call tracing** — `_TracedLLMProvider` transparent wrapper intercepts `generate()` calls, records prompt preview, response, latency, and estimated tokens via `asyncio.ensure_future`; wired in `get_llm_provider()`
- **Tool call tracing** — `_TracedTool` transparent wrapper intercepts `execute()` calls, records tool input, output preview, status, and latency; wired in `get_tool()`
- **History endpoints** — `GET /api/v1/tasks` (paginated list with optional status filter), `GET /api/v1/tasks/{trace_id}` (full detail with steps, LLM calls, tool calls, report), `GET /api/v1/tasks/{trace_id}/metrics` (consolidated metrics: duration, token counts, cost estimation, avg latencies)
- **Data Agent classifier** — New `classify_output` LangGraph node that uses LLM to split generated code into Python, SQL, or both with dedicated prompts (`data_classify_output_system`/`data_classify_output_user` v1.0.0); updated routing: `generate_code -> classify_output -> execute_python/execute_sql`
- **Documentation** — `docs/execution_db.md` with Mermaid ER diagram, table definitions, indexes, and relationship matrix; updated `docs/data_graph.md` with new `classify_output` node and edges

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| ContextVar over thread-local for trace_id | Async-native: ContextVar propagates automatically across `await` boundaries without manual threading. Each concurrent request gets its own isolated context. |
| Transparent wrapper pattern for LLM/tools | `_TracedLLMProvider` and `_TracedTool` wrap the real implementations without modifying their code. Observability is a cross-cutting concern, not business logic. |
| `asyncio.ensure_future` for DB writes in tracing | Fire-and-forget: recording LLM/tool calls to PostgreSQL does not block the agent node. If the DB write fails, only a warning is logged — the execution continues. |
| ExecutionMetricsCache as separate table | Pre-cached aggregated metrics avoid expensive COUNT/SUM queries on every metrics endpoint call. Updated on execution completion. |
| classify_output as a dedicated graph node | Isolates code classification from code generation, enabling independent iteration on the classification prompt without touching generation logic. |

### Key Learnings
1. **ContextVar discipline** — ContextVar requires explicit `token` management: every `set()` returns a token for `reset()`. The `trace_context` contextmanager pattern prevents context leaks between concurrent requests.
2. **Transparent wrappers over monkey-patching** — Wrapping the provider/tool instances at creation time (in `get_llm_provider()` and `get_tool()`) is cleaner than monkey-patching methods. The wrapper delegates all calls and adds observability transparently.
3. **Fire-and-forget DB writes are risky but practical** — `asyncio.ensure_future` for LLM call recording means DB failures are silently swallowed. In production, a background queue (Redis/Celery) would be better, but for a prototype this avoids adding latency to LLM calls.
4. **UUID handling across layers** — TypedDict state stores execution_id as `Optional[str]`, but the repository expects `UUID`. Consistent conversion at the boundary (with try/except fallback) prevents serialization errors.
5. **Code classification is surprisingly effective** — The LLM reliably splits Python+SQL outputs when prompted with JSON schema instructions. The `classify_output` node eliminated the previous ambiguity where the Data Agent would try to execute a mixed output as pure Python and fail.

---

## Week 7: Test Coverage, Code Quality Tooling & CI/CD

### Summary
This week was dedicated to hardening the codebase: comprehensive test expansion across all components (observability, tracing, synthesis, orchestrator, state manager, API error paths), introduction of code quality tooling (ruff, mypy, pre-commit hooks), a CI/CD pipeline via GitHub Actions, timezone-aware timestamp infrastructure, and several refactors driven by type checking and linting.

### Key Deliverables
- **Timezone-aware timestamps** — `backend/app/core/datetime_utils.py` with `now()` helper using configurable `TIMEZONE` env var; applied across execution repository, models, schemas base, and logging (`ContextFormatter.formatTime` with `ZoneInfo`)
- **Test expansion (~2,500+ lines of new tests):**
  - `test_observability.py` (453 lines) — `trace_context`, `trace_step` decorator, `TraceIDMiddleware`, `ExecutionRepository` CRUD, `_TracedLLMProvider`, `_TracedTool`
  - `test_tracing.py` (303 lines) — low-level `_try_record_llm_call` and `_try_record_tool_call` with UUID conversion edge cases, error handling, token estimation
  - `test_synthesis.py` (281 lines) — Synthesis Agent graph nodes (`collect_results`, `generate_synthesis`, `validate_report`), retry loop, max iterations
  - `test_orchestrator.py` (~650+ lines across commits) — orchestrator edges/helpers, error paths, re-planning, degradation detection
  - `test_state_manager.py` (83 lines) — Redis state CRUD with TTL
  - `test_api.py` (~195 lines added) — error handling and edge cases in endpoints, observability integration
  - `test_data_agent.py` — adjusted tests for recent agent changes (classify_output node)
  - `test_tools.py` — minor adjustments for compatibility
  - `pytest-cov` configured for coverage reporting (`pytest.ini`, `pyproject.toml`)
- **Code quality tooling:**
  - **Ruff** — `pyproject.toml` config (line-length 100, select `E/F/I/N/W/UP`), auto-fixes applied across 37 files
  - **mypy** — `pyproject.toml` config (`strict_optional`, `warn_unused_ignores`), type fixes across 21 files (~200 annotations improved: `X \| None` syntax, explicit return types, proper Optional handling)
  - **Pre-commit hooks** — `.pre-commit-config.yaml` with ruff (lint + format), mypy, trailing-whitespace, end-of-file-fixer, check-yaml/json, check-added-large-files
- **CI/CD pipeline** — `.github/workflows/ci.yml` with service containers (PostgreSQL 15, Redis 7), uv setup, ruff linting, `pytest --cov` with XML report, Codecov upload
- **Execution metrics from cache table** — `get_metrics()` in `ExecutionRepository` fetches from `ExecutionMetricsCache`; `GET /tasks/{trace_id}/metrics` endpoint returns cached metrics
- **Bug fixes & refactors** — Default env var values (`TIMEZONE`, `OLLAMA_BASE_URL`, etc.), mypy-driven type safety fixes, ruff formatting on remaining files, updated `requirements.txt`

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| Pre-commit hooks over CI-only linting | Catches formatting/type issues before commit, reducing CI feedback loops; ruff + mypy run in <2s locally |
| uv in CI | Consistent with local dev toolchain; `uv sync` is measurably faster than pip for dependency resolution |
| Service containers (Postgres + Redis) in CI | Tests exercise real DB and Redis connections rather than mocks-only, catching integration issues early |
| pytest-cov + Codecov | Coverage visibility helps identify untested paths; XML report uploads seamlessly to Codecov |
| TIMEZONE env var | Makes timestamps configurable per environment without code changes; falls back to America/Mexico_City |
| Centralized `datetime_utils.now()` | Single source of truth for current time, preventing timezone bugs across models, logs, and repository code |

### Key Learnings
1. **Type checking uncovers real bugs** — mypy's `strict_optional` and `warn_unused_ignores` caught potential `None` dereferences in tools (web_search, python_executor, sql_query), missing return annotations, and inconsistent `Optional` vs `None` handling across the codebase.
2. **Test observability components independently** — Testing `_try_record_llm_call` and `_try_record_tool_call` in isolation (test_tracing.py) before the higher-level traced wrappers made debugging UUID conversion and async fire-and-forget behavior straightforward.
3. **Pre-commit hook ordering matters** — Ruff lint + format must run before mypy because mypy checks the formatted code. Running mypy first produces false positives from unformatted line lengths or style violations that ruff would fix.
4. **Coverage without quality thresholds is vanity** — High line coverage doesn't guarantee correctness. The most valuable tests were the edge-case ones (invalid UUIDs, DB failures, malformed LLM responses), not the happy-path mocks.
5. **CI service containers are cheap but powerful** — GitHub Actions provides Postgres and Redis containers at no extra cost. The ~30s startup overhead is negligible compared to the confidence gained from running tests against real database and cache instances.

---

## Week 8: Frontend Implementation & Execution Metrics Persistence

### Summary
This week delivered the long-awaited React frontend from scratch, connecting the multi-agent backend to a real user interface. A complete single-page application was built with Vite, TypeScript, and React Router, featuring task creation, execution history, and detailed drill-down with live polling. On the backend side, execution metrics are now computed and persisted after every failure path, completing the observability feedback loop started in Week 6.

### Key Deliverables
- **Frontend scaffold** — Vite + React 19 + TypeScript + oxlint configured with full project structure (`frontend/`)
- **Routing & navigation** — `react-router-dom` v7 with 4 routes: `/`, `/tasks`, `/tasks/:traceId`, `*` (404); persistent layout with nav header and footer
- **API service layer** — `api.ts` with typed methods (`executeTask`, `listTasks`, `getTaskDetail`, `getTaskMetrics`), custom `ApiError` class, configurable timeout via `AbortController`, and centralized `handleResponse` for error extraction
- **HomePage** — Welcome message + `TaskForm` component with character counter (min 10), submit to `POST /api/v1/execute-task`, redirect to detail page on success
- **TaskListPage** — Paginated execution history table (`GET /api/v1/tasks`), `StatusBadge` for visual status indicators, Previous/Next pagination, loading/error/empty states
- **TaskDetailPage** — Full execution detail with metric cards (duration, LLM/tool calls, tokens, cost, errors), execution step list with status-colored cards, and report display; auto-polling every 5s for running/pending tasks
- **Reusable components** — `Layout`, `StatusBadge`, `ErrorMessage` (with retry callback), `LoadingSpinner`, `TaskForm`
- **Custom `useApi` hook** — Generic hook encapsulating loading/error/data state with `refetch` support
- **Dark theme** — CSS custom properties in `index.css` (dark color scheme), `styles.css` with utility classes, responsive typography
- **Centralized CSS refactor** — Consolidated styles from inline/page-level into `styles.css` for maintainability
- **Execution metrics computation** — `compute_and_upsert_metrics()` in `ExecutionRepository` using `INSERT ... ON CONFLICT DO UPDATE` with aggregated LLM calls, tool calls, steps, duration, and error counts; triggered on all orchestrator failure paths (planner, research, data, synthesis, degradation, max_steps)
- **Orchestrator type refinements** — `_sanitize_for_json` signature updated to `dict[str, Any]`, `build_orchestrator_graph` return type to `CompiledStateGraph`, improved None-safety across context builders and routing functions
- **Test expansion** — Orchestrator tests extended to cover execution metrics upsert on failure paths

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| Vite over CRA | Vite is the de facto standard for new React projects; instant HMR, native TypeScript, and faster builds. Outpaces CRA which is effectively deprecated. |
| React Router v7 | Latest version with improved data loading patterns; file-based routing not used to keep simplicity for a small SPA |
| Custom `ApiError` + `handleResponse` | Consistent error extraction with HTTP status, body, and truncated message; enables the frontend to display actionable error info |
| `useApi` custom hook | Encapsulates the fetch/loading/error/repeat pattern into a reusable abstraction, reducing boilerplate across pages |
| Auto-polling on detail page (5s interval) | Provides real-time progress feedback for long-running orchestrator executions without WebSocket complexity; interval cleared on unmount to prevent memory leaks |
| `compute_and_upsert_metrics` on failure paths | Metrics were previously only computed on successful completion; this ensures failed executions also have their data recorded for diagnostics and history queries |
| INSERT ... ON CONFLICT DO UPDATE | PostgreSQL-native upsert avoids race conditions between concurrent metric computations; idempotent by design |
| CSS custom properties for theming | Enables easy theme switching (light/dark) by changing a single `:root` block; all components reference the same variables |

### Key Learnings
1. **Frontend from scratch is fast with modern tooling** — Vite + React 19 + TypeScript scaffold to working multi-page app took ~4 days. oxlint catches TypeScript/React issues instantly with near-zero config.
2. **API service abstraction matters** — A centralized `api.ts` with typed methods, timeouts, and error handling prevented duplicated fetch logic across pages. The `AbortController` timeout pattern is cleaner than Promise.race.
3. **Polling is simple and effective for short-lived feedback** — The 5s polling on TaskDetailPage provides good UX for executions that typically run 30-300s. The cleanup-on-unmount pattern (`cancelled` flag + `clearInterval`) prevents race conditions.
4. **Fire-and-forget metrics computation has edge cases** — Calling `compute_and_upsert_metrics` after every failure path revealed UUID conversion and session management issues. The upsert pattern handles concurrent writes gracefully, but logging on failure was essential for debugging.
5. **Responsive design with CSS custom properties** — A single `:root` block with `@media (max-width: 1024px)` breakpoints for font-size keeps the app readable on mobile without component-level media queries.
6. **Type-safety across the frontend-backend boundary** — Defining `api.ts` types (ExecuteTaskResponse, ExecutionSummary, ExecutionDetail, ExecutionMetrics) that mirror the backend Pydantic schemas caught field mismatches early. The `resolveTraceId` pattern prevents routing parameter issues.

---

## Week 9: SSE Streaming, Toast Notifications & Plan Timeline (In Progress)

### Summary
Continued the frontend work with real-time execution progress. I completed through **Day 3** of the plan: the 5s polling on the detail page was replaced by a Server-Sent Events (SSE) stream (`GET /api/v1/tasks/{trace_id}/stream`), a React Context + useReducer toast notification system was added, and a vertical PlanTimeline component now visualizes the execution plan with per-step status. On the backend, the generated plan is now persisted in a JSON column on the `Execution` model (served by both history and stream endpoints), and the Data Agent gained a self-reflection node that analyzes execution errors and produces a fix plan before retrying code generation. Days 4–7 of the plan (TanStack Query, stats dashboard, search/filtering, retry button, performance optimizations) remain pending and will be carried to Week 10.

### Key Deliverables
- **SSE streaming endpoint** — `sse-starlette>=3.4.6` added; new `backend/app/api/routes/stream.py` with `EventSourceResponse` and an async generator that polls the execution every 1s, emitting a `progress` event (status, steps with ids, plan) only when something changed, a `complete` event with metrics and report on terminal statuses, and `error` events on failures or missing executions
- **Router registration & fixes** — stream router registered in `main.py`; fixed the `api/v1` prefix missing leading slash and removed `response_model=EventSourceResponse` which broke the route
- **`useEventSource` hook** — `frontend/src/hooks/useEventSource.ts` wrapping the browser `EventSource` with `progress`/`complete`/`error` listeners, a `completed` flag to suppress reconnection errors, cleanup on unmount, and a `close()` callback
- **TaskDetailPage streaming refactor** — replaced the 5s polling interval with `useEventSource`; `mergeSteps` merges streamed steps by stable id instead of replacing the whole list; detail loads first, metrics second with 404 tolerated; `API_BASE`/`ApiError` exported from the API service
- **Toast notifications** — `frontend/src/components/ToastProvider.tsx` with `createContext` + `useReducer` (`addToast`/`removeToast`/`useToast`), auto-dismiss after 4s, slide-in animation; `App.tsx` wrapped with the provider; toasts wired into `TaskForm` (success/error on submit) and `TaskDetailPage` (load errors, metrics unavailable, completion with error count)
- **Toast CSS refactor** — inline styles moved to `styles.css` as `.toast-container`/`.toast--success|error|info` classes with dark-theme-consistent colors
- **PlanTimeline component** — `frontend/src/components/PlanTimeLine.tsx` rendering a vertical timeline with per-step-type icons (scoping/research/analysis/synthesis), status-colored markers and labels, connector lines, and a pulse animation for running steps (~128 lines of CSS)
- **Execution plan persistence** — `plan` JSON column on the `Execution` model; `update_execution` and `run_planner` persist the generated plan; `ExecutionDetail` schema and the SSE payload now include it
- **Timeline logic in detail page** — `Plan`/`PlanStep` types in `api.ts`; `toTimelineSteps` maps execution steps (per agent: planning/research/data_analysis/synthesis) to plan steps, using the last recorded status per step type as the truth while the execution runs
- **Data Agent self-reflection on retry** — new `reflect_error` LangGraph node that asks the LLM to diagnose the execution error and emit a concrete fix plan; new versioned prompts (`data_reflect_error_system`/`data_reflect_error_user` v1.0.0); retry edges re-routed from `execute_python`/`execute_sql` → `reflect_error` → `generate_code`; `reflection` field added to `DataState` and to the code-gen prompt
- **Markdown-safe code generation** — `_strip_markdown_code` helper strips fenced code blocks from LLM output; the code-gen prompt now requests raw code without markdown; `classify_output` parsing also hardened
- **Robustness & typing fixes** — mypy fixes across route modules (data, history, llm, orchestrator, plan); None-safe integer casts for latency/token/duration fields in history serialization; stream endpoint fetches steps by `execution.id` instead of casting `trace_id`
- **Docs** — `docs/data_graph.md` updated with the `reflect_error` node, `reflection` state field, and new edges

### Architecture Decisions Worth Highlighting
| Decision | Rationale |
|----------|-----------|
| SSE over client polling | The backend pushes events only when state changes (server-side 1s poll with diff detection); the client keeps one persistent HTTP connection instead of firing a request every 5s |
| Server-Sent Events over WebSocket | Unidirectional progress monitoring does not need a bidirectional channel; SSE is plain HTTP, auto-reconnects, and is dramatically simpler to integrate with FastAPI (`EventSourceResponse`) and the browser (`EventSource`) |
| Diff-based event emission in the generator | Tracking `last_status`/`last_step_count` and yielding only on change minimizes bandwidth and avoids redundant React re-renders |
| Merge-by-id on the frontend | Streamed steps carry stable ids and are merged into a `Map`, preserving previously loaded steps and preventing flicker that full-list replacement would cause |
| `plan` persisted as a JSON column | One source of truth for the generated plan, served by both the history detail endpoint and the SSE stream — no plan regeneration or separate storage |
| reflect_error as a dedicated graph node | Debugging is separated from generation: the LLM analyzes the error and produces an explicit fix plan that the code-gen prompt consumes on retry, replacing the previous raw-error-only retry with structured self-correction |
| Prompt-level markdown ban + defensive stripping | Even with the prompt forbidding code fences, LLMs still emit them; stripping markdown blocks defensively makes code execution robust to formatting drift |
| Toast system with Context + useReducer | Zero-dependency global UI feedback; the provider pattern keeps state management isolated and the `useToast` hook makes it usable anywhere in the tree |

### Pending (carried to Week 10)
- [ ] TanStack Query (React Query) refactor of `useApi` with caching, retry, and refetch-on-focus
- [ ] Stats dashboard (`GET /api/v1/stats` endpoint + `DashboardPage` with aggregated metrics)
- [ ] Search & filtering on `TaskListPage` (debounced `q` parameter, status filter, URL search params)
- [ ] Retry button for failed tasks (`POST /api/v1/tasks/{trace_id}/retry`)
- [ ] Performance optimizations (React.lazy + Suspense, useMemo/useCallback)
- [ ] Responsive design refinements (mobile media queries)
- [ ] Agent graph visualization (React Flow / D3.js) and LogViewer

### Key Learnings
1. **SSE is deceptively simple but has sharp edges** — `EventSourceResponse` + a generator with `asyncio.sleep(1)` is a clean push pattern, but `response_model=EventSourceResponse` breaks the route, the prefix needs the leading slash, and `asyncio.CancelledError` must be caught to close connections cleanly on client disconnect.
2. **Browser EventSource quirks** — It auto-reconnects and fires the `error` listener on every failed attempt, so a `completed` flag is required to avoid spurious error toasts after a normal `complete` event. It also cannot send custom headers, which matters if auth is added later.
3. **Merge-by-id beats replace** — Streaming steps with stable ids and merging client-side preserves continuity of already-rendered steps and avoids UI flicker; keying the merge on `step.id` (an issue found and fixed during the week) is essential.
4. **Reflection-driven retry improves self-correction** — Giving the code-gen LLM a prior error diagnosis with a concrete fix plan (the `reflect_error` node) is more effective than feeding the raw error. The prompt still needs to forbid markdown, and the agent must defensively strip fences anyway — LLM output formatting cannot be fully trusted.
5. **Real data exposes None-safety gaps** — The first streaming runs revealed `None` latency and token fields in history serialization; `int()` casts must be guarded against `None` before they reach the response schema.
6. **Realistic weekly scope** — Three focused features (streaming, toasts, timeline) plus backend support work is a full week at 1–2h/day. Days 4–7 are substantial enough to warrant their own week rather than a rushed Sunday.
