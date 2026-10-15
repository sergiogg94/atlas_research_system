# Code Review — Diagnostic prior to publishing as a portfolio piece

**Repository:** `atlas_research_system` · **Date:** 2026-10-15 · **Scope:** diagnostic only (no proposed solutions)

---

## PART A — System map

### A1. Agents, roles and orchestration

All agents are LangGraph `StateGraph`s compiled on demand (`build_*_graph()`), defined in `backend/app/core/agents/` and orchestrated by a master graph in `backend/app/core/orchestrator.py`.

| Agent | File | Role | Nodes | Limits |
|---|---|---|---|---|
| **Planner** | `agents/planner.py` | Decomposes the task into a Pydantic `Plan` (objective + 3–7 steps with `step_type`) | `validate → generate (LLM) → parse` | No retries; error → END with `error` in state |
| **Research** | `agents/research.py` | For each step in the plan: `parse_step → web_search (ddgs) → scrape top-3 URLs (httpx+BS4) → synthesize_finding (LLM)` | 4 nodes in a loop | Iterates until `steps` are exhausted; any tool failure → error → END |
| **Data** | `agents/data.py` | Data analysis: `analyze_task → generate_code → classify (python/sql/both) → execute_python/execute_sql → reflect_error` | 6 nodes | Retry via `reflect_error → generate_code` while `iteration < 3` (hardcoded) |
| **Synthesis** | `agents/synthesis.py` | `collect_results (stub) → generate_synthesis (LLM) → validate` | 3 nodes | `MAX_ITERATIONS = 3`; `collect_results` does nothing real |

**Orchestrator** (`orchestrator.py:826`, `build_orchestrator_graph`): nodes `run_planner → check_max_steps → run_research → check_max_steps → run_data? → check_max_steps → run_synthesis → END`, with:

- **Conditional routing**: `route_after_check` decides research/data/synthesis based on `current_agent` and `_check_if_data_needed()` (keyword heuristic over the plan steps: "analysis", "calculate", …).
- **Re-planning**: any error → `re_plan` (a node that asks the LLM for a JSON `{"decision": "retry"|"skip"|"abort"}`) → `check_degradation` → retry the failed agent, skip to the next one, or END.
- **Hard limits**: `MAX_TOTAL_STEPS = 50` (→ status `TIMEOUT`) and `DEGRADATION_THRESHOLD = 3` consecutive failures on the same agent (→ `FAILED`). In addition, `/execute-task` wraps `graph.ainvoke` in `asyncio.wait_for(…, 600s)` → HTTP 504.
- **State**: `OrchestratorState` (TypedDict) with task_description, plan, plan_steps, research_findings, data_results, report, error, current_agent, total_steps, checkpoint_idx, consecutive_failures, last_failure_agent, trace_id, execution_id.

### A2. End-to-end flow

1. **UI** (`POST /api/v1/execute-task`, `routes/orchestrator.py`) receives `{task_description}`, takes the `trace_id` from the middleware (`X-Trace-ID` header or uuid4) and invokes the orchestrator graph with a 600 s timeout (synchronous execution inside the HTTP request).
2. **`run_planner`** creates the `executions` row (status `running`) in PostgreSQL via `execution_repository`, records a step, invokes the Planner subgraph and persists `objective`, `plan` and `plan_steps`.
3. **`run_research`** iterates over the plan steps with web search + scraping + LLM summary; persists `research_findings` and one step per agent.
4. **`run_data`** (only if the keyword heuristic decides so) executes LLM-generated Python/SQL code in a sandbox, with a reflection-retry loop ≤ 3.
5. **`run_synthesis`** generates the final markdown report, marks the execution `completed` and computes metrics (`compute_and_upsert_metrics`).
6. Each node saves a checkpoint of the sanitized state in **Redis** (`orchestrator:{uuid}`, TTL 1 h) — write-only, there is no resume.
7. In parallel, the UI subscribes to `GET /tasks/{trace_id}/stream` (SSE, 1 s polling against the DB with change detection) and receives `progress` and `complete` events (with report and metrics).
8. **Failure paths**: each agent node marks the execution `failed`, records the failed step and propagates `error` → `re_plan` decides retry/skip/abort → `check_degradation` aborts after 3 consecutive failures.

### A3. Persistence

| Where | What | Why |
|---|---|---|
| **PostgreSQL** (`models/execution.py`) | `executions` (identity, plan JSON, status, report), `execution_steps` (per-agent trace), `llm_calls` (full prompts, responses, estimated tokens), `tool_calls` (input JSON, output preview), `execution_metrics_cache` (materialized aggregates via `ON CONFLICT` upsert) | Auditable history + responses for `/tasks`, `/stats`, SSE |
| **Redis** (`state_manager.py`, TTL 1 h) | `orchestrator:{id}` — JSON snapshot of the state after each node; `research:{id}` exposed but not used by the orchestrator | "Cheap" checkpoints for debugging; resume pending (documented) |
| **Does not persist** | Standalone runs of `/plan`, `/research`, `/data` | Decision #11 of the decision log |

Sessions: each method of `ExecutionRepository` opens its own `SessionLocal` (no shared session and no unit-of-work).

### A4. LLM providers

- Interface `LLMProvider` (`llm/base.py`): `generate(prompt, system)` + `list_models()`, both async.
- **Factory** (`llm/factory.py`): registry dict `{"echo": EchoProvider, "ollama": OllamaProvider}` + extensible `register_provider()`; selection via `settings.llm_provider` (env `LLM_PROVIDER`, default `echo`); if the key does not exist, it silently falls back to Echo.
- **OllamaProvider**: HTTP to `/api/generate` and `/api/tags` with `httpx` (60 s timeout), tenacity retry (3 attempts, exponential backoff 2–10 s) only on `httpx.TimeoutException|NetworkError`. Default model `qwen2.5:7b`.
- **EchoProvider**: deterministic responses for tests/CI.
- Every provider is wrapped in `_TracedLLMProvider` (tracing.py), which persists each call in `llm_calls` (tokens = `len//4`). Every tool is wrapped in `_TracedTool` → `tool_calls`.

### A5. Application layers

```
frontend/ (React 19 + Vite + TanStack Query + react-router; SSE via EventSource)
   │ HTTP + SSE (nginx proxy /api/v1)
backend/app/api/routes/     → FastAPI routers (/api/v1: health, llm, plan, research, data,
   │                            orchestrator, history, stream, stats, retry)
backend/app/schemas/        → Pydantic request/response (1 file per domain)
backend/app/core/agents/    → LangGraph subgraphs (planner, research, data, synthesis)
backend/app/core/orchestrator.py → master graph
backend/app/core/prompts/   → PromptTemplate registry (versioned Python classes)
backend/app/core/tools/     → BaseTool registry (web_search, web_scraper, python_executor, sql_query)
backend/app/core/llm/       → provider factory (echo, ollama) + tenacity retry
backend/app/core/           → database (async SQLAlchemy), execution_repository, state_manager
                              (Redis), logging (colorlog+ContextVars), middleware (trace_id), tracing
backend/app/models/         → ORM (Execution, ExecutionStep, LLMCall, ToolCallRecord, metrics cache)
```

Cross-cutting observability: `TraceIDMiddleware` injects `trace_id` into ContextVars; `@trace_step` measures per-agent latency; the traced proxies persist LLM/tool calls fire-and-forget (`asyncio.ensure_future`).

### A6. Infrastructure

- **Docker**: `backend/Dockerfile` (python:3.13-slim + `requirements.txt`, `uvicorn --reload`); `frontend/Dockerfile` multi-stage (node:22 build → nginx:alpine with SSE-safe proxy `proxy_buffering off`); `docker-compose.yml` with backend + postgres:15 + redis:7 + frontend (:8080), bind-mount of `./backend/app` and `extra_hosts` for the host's Ollama.
- **CI** (`.github/workflows/ci.yml`): ruff over `backend/app/` + pytest with Postgres/Redis services + upload to Codecov. `uv sync` as the install step.
- **Deployment**: local only via compose. No remote environment, no migrations (Alembic) and no deploy pipeline.
- **Local tooling**: pre-commit (ruff, mypy, basic hooks), pytest.ini with `--cov-fail-under=75`, oxlint + vitest on the frontend.

---

## PART B — Inconsistencies

Severity: **critical** = breaks real functionality of the main flow or of the portfolio; **important** = debt a senior reviewer would flag; **minor** = polish.

### B1. Agent construction patterns — not all the same

| Finding | File(s) | Severity |
|---|---|---|
| `run_planner` does not use the `@with_checkpoint` wrapper like the other 3 nodes; it calls `save_checkpoint` manually → two persistence patterns in the same file | `orchestrator.py:152-257` vs `:260-262` | minor |
| In Planner, `validate_task` and `parse_plan` are sync and `generate_plan` is async; in Research, `parse_step` is `async` without any `await` (and so is the rest) → the sync/async criterion per node is not consistent | `agents/planner.py`, `agents/research.py:24` | minor |
| Synthesis's `collect_results` is a stub that only does `{**state}` — a full graph node does nothing | `agents/synthesis.py:25-32` | minor |
| Detectable copy-paste: `build_synthesis_graph` logs *"Planner StateGraph compiled successfully"* and its errors as *"Failed to compile planner"* | `agents/synthesis.py:131-134` | minor |
| Agent error handling: the try/except block + `result["error"]` branch + `update_execution(FAILED)` + `compute_and_upsert_metrics` + `_record_execution_step(failed)` is almost identical ×4 (~55 lines each, ~220 total duplicated lines) | `orchestrator.py:184-224, 292-334, 394-436, 538-580` | important |
| Iteration limits with three different mechanisms: constant `MAX_ITERATIONS=3` (synthesis), hardcoded counter `iteration < 3` in the routers (data), module constant `MAX_TOTAL_STEPS=50` (orchestrator) | `synthesis.py:10`, `data.py:186,197`, `orchestrator.py:45` | minor |
| Synthesis's `collect_results` + validation is a "re-invention" of the Planner's validation pattern (parse/validate), solved a different way | `synthesis.py:64-100` vs `planner.py:63-90` | minor |

### B2. Prompts

| Finding | File(s) | Severity |
|---|---|---|
| Most prompts live in a versioned registry (`core/prompts/`, ABC classes + `get_prompt()`), **but the `re_plan` prompt is hardcoded as an inline f-string** in the orchestrator — two ways of managing prompts in the same system | `core/prompts/*` vs `orchestrator.py:653-666` | important |
| `PromptTemplate.template` is declared `@property @abstractmethod` but every subclass defines it as a plain class attribute (implicit overload of the ABC contract) — it works, but the ABC does not deliver what it promises | `prompts/base.py:8-11` vs all prompt files | minor |
| Incorrect copy-paste descriptions: the Synthesis prompts describe *"System prompt for data analysis agent"* / *"User prompt for data analysis agent"* | `prompts/synthesis.py:20,34` | minor |
| The CodeGen system prompt lists allowed libraries (pandas, numpy, matplotlib) that must be kept manually in sync with the sandbox's `ALLOWED_IMPORTS` — two sources of truth for the same policy | `prompts/data.py:43-45` vs `tools/python_executor.py:8-24` | important |

### B3. Duplicated/contradictory state schemas and data models

| Finding | File(s) | Severity |
|---|---|---|
| **Orphan `Task`/`TaskStatus` model**: nothing in the application uses it; only `init_db.py` imports it (creates an empty, useless `tasks` table on every deployment). It is the week-1 model, replaced by `Execution`, but it is still alive | `models/task.py`, `scripts/init_db.py:11`, `models/__init__.py:2` | important |
| `OrchestratorState.step_index` and `max_steps` are declared and passed in the initial `ainvoke`, but are **never read**: `check_max_steps` uses the module constant `MAX_TOTAL_STEPS` and `step_index` is not used in any routing | `orchestrator.py:34-36,782-806`, `routes/orchestrator.py:29-33` | important |
| `OrchestratorState.data_results: list | None` but `run_data` stores `result["execution_result"]`, which is a **dict** (`{stdout, stderr, returncode, rows…}`); Synthesis serializes it with indiscriminate `str()` | `orchestrator.py:454`, `agents/data.py:144-148`, `synthesis.py:53` | important |
| `trace_id` declared in the TypedDicts of the 4 sub-agents but never passed by the orchestrator in the `ainvoke` calls — a dead field in all states | `planner.py:19`, `research.py:21`, `data.py:24`, `synthesis.py:22` | minor |
| Double ORM style in the same file: `Execution` with SQLAlchemy 2 `Mapped/mapped_column`, the rest of the tables with classic `Column` | `models/execution.py:25-46` vs `:52-142` | minor |
| `ToolCallDetail.input` typed `str | None` in the API schema but is `JSON` in the model; the route converts it with `str()`. In addition, `history.py` converts **every** None with `str()` → `input_summary: "None"` (literal string) in responses | `schemas/history.py:64`, `api/routes/history.py:99-105` | important |
| `DataRequest.max_iterations` exists in the schema but the route ignores it (passes `iteration: 0` and the graph uses the hardcoded 3) | `schemas/data.py:9`, `routes/data.py:26-31` | minor |
| Frontend types out of sync with the backend: TS `ExecutionDetail` omits `llm_calls`/`tool_calls` that the endpoint does return; comments with a typo referencing the wrong file ("hisory.py") | `frontend/src/types/api.ts:60-67` | minor |

### B4. Error handling, logging and configuration — no single style

| Finding | File(s) | Severity |
|---|---|---|
| **The logger is misattributed**: `logger = logging.getLogger(__name__)` lives *inside* `core/logging.py`, and all modules do `from app.core.logging import logger` → the logger name is always `app.core.logging` and `%(module)s`/`%(funcName)s` in the format always show the logging module, not the actual module emitting the log | `core/logging.py:71` + all modules | important |
| `dictConfig` and `get_settings()` run at module level → global side effects when importing anything that touches logging (import-time side effects, hard to test) | `core/logging.py:29,69` | minor |
| Routes `/plan`, `/test/generate`, `/test/models` catch `TimeoutError` but there is **no `asyncio.wait_for`** in those routes → the except blocks are dead code; also, Ollama raises `httpx.TimeoutException`, which is not `TimeoutError` | `routes/plan.py:27-29`, `routes/llm.py:24-27,42-45` | important |
| Inconsistent standalone timeouts: `/data` 180 s, `/research` 600 s, `/plan` none | `routes/data.py:22`, `routes/research.py:31` | minor |
| `POST /task/{trace_id}/retry` duplicates ~40 lines of the `/execute-task` handler (full copy-paste of the invoke block + response) | `routes/retry.py:22-48` vs `routes/orchestrator.py:21-45` | important |
| Config: `Settings` keeps both the full `database_url` and the `postgres_user/password/host/port/db` fields that nobody uses to connect — two sources of truth for the same configuration | `config.py:11-16` | minor |
| Insecure defaults for a portfolio: `debug=True` (enables SQLAlchemy `echo`, verbose), `log_level="DEBUG"` as the default in production | `config.py:23-24`, `core/database.py:9` | minor |
| `.env.example` mixes conventions: `llm_provider=ollama` in lowercase, the rest of the variables in uppercase (works due to pydantic-settings case-insensitivity, but it is noise) | `.env.example` | minor |
| `redis_client.py` defines a lazy Redis client, but `/health` creates its own `redis.from_url` and closes it per request — two parallel Redis clients | `core/redis_client.py`, `routes/health.py:24-30` | minor |
| In `factory.py` there is a commented-out Spanish block for a "cached singleton" that was never implemented (the week-1 development log presents it as a decision taken) | `llm/factory.py:32-47` | minor |

### B5. Sync/async without a clear criterion

| Finding | File(s) | Severity |
|---|---|---|
| `WebSearchTool.execute` is `async` but calls **synchronous** `DDGS()` (real network) → blocks the uvicorn event loop for the entire search | `tools/web_search.py:28-34` | important |
| `PythonExecutorTool` runs **synchronous** `subprocess.run` with a 30 s timeout inside an async node → any code execution freezes the event loop (SSE, health checks, other requests) for up to 30 s | `tools/python_executor.py:140-147` | important |
| The rest of the stack (async SQLAlchemy, async httpx, redis.asyncio, sse-starlette) is rigorously async — the event-loop blocking in the tools is the only point that breaks the model and it is not documented in the decision log | `tools/*` vs `core/*` | important |

### B6. Dependency management

| Finding | File(s) | Severity |
|---|---|---|
| Source of truth: `pyproject.toml` + `uv.lock`; `requirements.txt` is correctly generated with `uv pip compile` and synced (Jul 2026). **But** there is no dev/prod separation: `pytest`, `pytest-cov`, `mypy`, `ruff`, `pre-commit` are in the main `dependencies` → the production Docker image installs the entire development toolchain | `pyproject.toml:7-30`, `requirements.txt` (mypy, ruff, pytest…), `backend/Dockerfile` | important |
| pre-commit out of sync with pyproject: mypy hook `v1.15.0` vs required `mypy>=2.3.0`; ruff hook `v0.11.0` vs `ruff>=0.15.21` | `.pre-commit-config.yaml` vs `pyproject.toml` | important |
| mypy is configured (`[tool.mypy]`, pre-commit) but **does not run in CI** — the README quality badge mentions mypy and only ruff runs | `.github/workflows/ci.yml:42-43`, `README.md:74` | important |
| `matplotlib` is in the sandbox allowlist and in the Data agent prompts, but **is not a dependency** → any LLM code that does `import matplotlib` always fails at runtime | `tools/python_executor.py:13-14`, `prompts/data.py:32,43` | important |
| `numpy`/`pandas` are main runtime dependencies (justified: the sandbox subprocess uses them), but without a note or separation explaining why the backend needs them | `pyproject.toml:17-18` | minor |
| `scripts/generate_requirements.sh` duplicates a one-line command already documented in AGENTS.md/README and lacks a trailing newline | `scripts/generate_requirements.sh` | minor |

### B7. Drift between README/docs and code

| Finding | File(s) | Severity |
|---|---|---|
| `docs/development_log.md` (week 10) claims that a *"GitHub Actions manual-QA workflow plus issue templates"* was added — the repo **only has** `.github/workflows/ci.yml`; there are no issue templates or QA workflow. In a portfolio, a claim the repo contradicts is a red flag | `docs/development_log.md` (week 10), `.github/` | important |
| `docs/orchestrator_graph.md` points to `app/core/agents/orchestrator.py` as the source (the real path is `app/core/orchestrator.py`) and its state table omits `trace_id`, `execution_id` and `last_step_latency_ms` — a generated doc not regenerated after the changes | `docs/orchestrator_graph.md:3` | important |
| `docs/development_log.md` (week 8) presents 5 s *polling* as an architecture decision and week 1 replaces it with SSE — the log is fine as a diary, but next to the decision log it can be confusing; the README only mentions SSE (correct) | `docs/development_log.md` | minor |
| Week 1 log describes *"Factory + cached singleton"* as a decision taken; the singleton is commented out and does not exist | `docs/development_log.md` (week 1), `llm/factory.py:32-47` | minor |
| `AGENTS.md` still describes `task.py: Task` as an active model of the data layer (it is orphaned, see B3) | `AGENTS.md` (Architecture notes) | minor |
| `frontend/README.md` is the default Vite template, unmodified (it talks about "Oxlint rules", React Compiler, etc.) — noise at the frontend root | `frontend/README.md` | minor |
| `docs/api.md` documents the 504 for `/plan` on timeout, but that route has no `wait_for` (dead code, see B4) | `docs/api.md`, `routes/plan.py` | minor |
| Strength worth highlighting: README, ARCHITECTURE.md, api.md and the decision log are generally **very aligned** with the code (known limitations honestly declared: write-only checkpoints, sandbox is not a container, cost=0, retry creates a new execution) | `README.md`, `docs/ARCHITECTURE.md` | — |

### B8. Orphaned code, files, env vars and models from earlier approaches

| Finding | File(s) | Severity |
|---|---|---|
| `models/task.py` (`Task`, `TaskStatus`) — leftover from the week-1 approach, replaced by `Execution`; creates a `tasks` table on every `init_db` | `models/task.py` | important |
| `frontend/src/hooks/useApi.ts` — generic fetching hook **replaced by TanStack Query** (week 10) but the file is still exported and compiled; two data-fetching systems coexist | `frontend/src/hooks/useApi.ts`, `useTasks.ts` | important |
| Commented-out toast-test code block in Spanish inside the detail page (buttons "Operación exitosa", "Algo salió mal") | `frontend/src/pages/TaskDetailPage.tsx:109-112` | minor |
| Comment with the previous signature of `SQLQueryTool.execute` (`# async def execute(self, query: str, params…)`) next to the `*args/**kwargs` implementation | `tools/sql_query.py:24-25` | minor |
| Commented-out Spanish code for the LLM singleton | `llm/factory.py:32-47` | minor |
| `planning/` (local, untracked folder): planning notes in Spanish with informal names (`reporte_salchica.md`, `agregar_logs.md`, `errores_mypy.md`) and `.claude/settings.local.json` are **not in `.gitignore`** — risk of them slipping into a `git add .` before publishing | `planning/`, `.claude/`, `.gitignore` | important |
| Local coverage artifacts (`.coverage`, `htmlcov/`, `backend/htmlcov/`) are ignored, but `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/` are **not** listed in `.gitignore` | `.gitignore` | minor |
| `StateManager.save/get_research_state` (`research:{id}` in Redis) is not used by any orchestration path (acknowledged in ARCHITECTURE §8, but the code stays as a dead API) | `core/state_manager.py:6-14` | minor |

### B9. Duplicated logic (same problem solved twice)

| Finding | File(s) | Severity |
|---|---|---|
| Agent-failure handling block ×4 in the orchestrator (see B1) | `orchestrator.py` | important |
| `routes/retry.py` ≈ `routes/orchestrator.py` (same handler copied) | `routes/retry.py`, `routes/orchestrator.py` | important |
| Three mechanisms for persisting/checkpointing the orchestrator state coexisting: `save_checkpoint` + `_sanitize_for_json` (sanitized), `with_checkpoint` (not sanitized, stores `dict(result)` directly) and the manual per-node `update_execution` calls — with different semantics among them | `orchestrator.py:50-109` | important |
| `total_steps` is incremented with the same computation in two places per node (`update_execution` and the state return) — double maintenance of the same counter | `orchestrator.py:336-355, 438-457` | minor |
| `MetricCard` is defined twice (identical) on two frontend pages | `DashboardPage.tsx`, `TaskDetailPage.tsx` | minor |
| LLM output "markdown stripping" is solved in the Data agent (`_strip_markdown_code`) and, in the rest of the system, with prompt instructions ("Return only raw text/JSON") — two strategies for the same LLM-formatting problem, with no shared helper | `agents/data.py:27-33` vs `prompts/research.py:15`, `prompts/planner.py:22-23` | minor |

### B10. Critical functional bugs (they block the main flow)

These four findings imply that the happy path documented in the README **does not work end-to-end today**:

| # | Finding | File(s) | Severity |
|---|---|---|---|
| 1 | **The frontend calls retry with GET**: `api.retryTask` does `fetch(url)` without `method: "POST"`; the backend defines `POST /task/{trace_id}/retry` → 405 Method Not Allowed. The UI "Retry Task" button is broken | `frontend/src/services/api.ts:93-95` vs `routes/retry.py:13` | **critical** |
| 2 | **`return HTTPException` instead of `raise`**: when the execution does not exist, the route returns an `HTTPException` object as a 200 body (and with the typo "Execturion") instead of responding 404 | `routes/retry.py:20` | **critical** |
| 3 | **The `task_id` in the response corresponds to nothing**: `/execute-task` and `/retry` generate a local `task_id = str(uuid4())`, unrelated to either `execution_id` or `trace_id`. The frontend navigates to `/tasks/{task_id}` after creating and after retrying, and `TaskDetailPage` looks up that id → **"Task not found" in the main creation flow** | `routes/orchestrator.py:25`, `routes/retry.py:21`, `TaskForm.tsx`, `TaskDetailPage.tsx:68` | **critical** |
| 4 | **Retrying the Planner re-crashes the execution**: `re_plan` with decision `retry` re-invokes `run_planner`, which **always** calls `create_execution(trace_id=…)` *outside* its try block — with the `UNIQUE` on `executions.trace_id`, a planner that fails twice raises `IntegrityError` that escapes the graph → HTTP 500, with no degradation or controlled abort | `orchestrator.py:161-165` (outside the try at `:184`), `route_after_replan` (`:739-745`) | **critical** |

### B11. Naming and structure conventions

| Finding | File(s) | Severity |
|---|---|---|
| Mixed Spanish/English in comments and artifacts: "Asegurar que todo sea JSON-serializable", "Limpiar recursivamente", "Para mantener un singleton", "# Cobertura" in `.gitignore`, `init_db.py` with Spanish emojis, the entire `planning/` folder in Spanish — the source code is in English but the Spanish leftovers betray the process | `orchestrator.py:54,77`, `factory.py:32`, `.gitignore:15`, `scripts/init_db.py` | important |
| Systematic typos in visible identifiers/comments: `Originl`, `plam`, `Scecurity`, `Stepts`, `Recived`, `Excecuting`, `Execturion`, `complite`, `pupeline`, `hisory`, `Unic name` | `orchestrator.py:25-36`, `research.py:14`, `routes/data.py:18`, `routes/retry.py:20`, `api.ts:55,61`, `types/api.ts:33`, `tools/base.py:18` | important |
| The `/research` handler is named `create_plan` (copy-paste from the plan router) — confusing when reading OpenAPI/logs | `routes/research.py:19` | minor |
| Inconsistent frontend component naming: `PlanTimeLine.tsx` (Timeline as two words) — and the test file replicates that name | `frontend/src/components/PlanTimeLine.tsx` | minor |
| Two `scripts/` folders with different responsibilities and no clear convention: `scripts/` (root, repo utilities) and `backend/scripts/` (init_db, agent docs generator) | `scripts/`, `backend/scripts/` | minor |
| Three stylesheets imported at once in the frontend (`App.css`, `styles.css`, `index.css`) with no documented hierarchy | `frontend/src/App.tsx:5-6` | minor |
| `docker-compose.yml` + `Dockerfile` mix dev and "prod": `--reload` in the image CMD, code bind-mount, yet presented as the README's deployment method | `backend/Dockerfile:10`, `docker-compose.yml:16-17` | minor |

### B12. Observability and security (portfolio context)

| Finding | File(s) | Severity |
|---|---|---|
| The SQL tool queries the **same database** as the application with the same user — "read-only" is only the static regex/blacklist validation (acknowledged in the decision log, but the dedicated DB role does not exist) | `tools/sql_query.py`, `core/database.py` | important |
| CORS `allow_origins=["*"]` together with `allow_credentials=True` (invalid/permissive combination, acknowledged in §10) | `main.py:31-37` | minor |
| Starlette's `BaseHTTPMiddleware` (known overhead) for something as simple as injecting a header | `core/middleware.py` | minor |
| Sandbox success is defined as `returncode == 0 and not stderr` — any warning printed to stderr marks the execution as failed and triggers the reflection loop | `tools/python_executor.py:56` | minor |
| History search with `LIKE %q%` without escaping the user's `%`/`_` (pattern injection, not SQL injection) | `execution_repository.py:133` | minor |

---

## Summary by severity

- **Critical (4)** — all in the retry/creation flow: retry invoked with GET, `return HTTPException`, phantom `task_id` that breaks navigation after creating a task, and `IntegrityError` when retrying the Planner (B10).
- **Important (~20)** — orphaned Task agent + dead table; orphaned `useApi` coexisting with TanStack Query; inline `re_plan` prompt; error-handling ×4 duplicated in the orchestrator; logger misattributed in all logs; dead timeout excepts; matplotlib in prompts/allowlist without being installed; dev-deps in the Docker image; pre-commit out of sync and mypy absent from CI; development_log claims a workflow that does not exist; stale orchestrator docs; `planning/` and `.claude/` not gitignored; event-loop blocking in `web_search` and `python_executor`; `data_results` typed `list` but is a dict; `str(None) → "None"` in history responses; systematic typos and Spanish comments in an English codebase.
- **Minor (~25)** — mixed styles across agents, stubs (`collect_results`), copy-paste in synthesis logs, dead state fields (`step_index`, `max_steps`, `trace_id` in sub-states), double ORM style, config with duplications and insecure defaults, `MetricCard` duplicated in the frontend, untouched Vite README, `PlanTimeLine` naming, etc.

**Overall read for the portfolio:** the architecture (LangGraph + tracing + persistence + SSE + decision log) is solid and the design documentation is remarkably honest; but the 4 critical bugs in the create→view→retry flow and the orphans from earlier iterations are the first thing a reviewer or recruiter would run and find.
