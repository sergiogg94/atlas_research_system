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
