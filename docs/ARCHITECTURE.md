# Atlas Research System — Architecture

Multi-agent research system that receives a complex task, decomposes it into a plan, researches it on the web, performs data analysis, and synthesizes a final report. The backend is a **FastAPI** application orchestrating **LangGraph** agent graphs asynchronously, backed by **PostgreSQL** (persistence/history) and **Redis** (state checkpoints), with **Ollama** as the local LLM and a **React** frontend for task creation and live progress viewing.

## 1. System design

```mermaid
graph TD
    subgraph CLIENT["Client"]
        USER["👤 User"]
        BROWSER["🌐 React App<br/>React 19 · Vite · TanStack Query<br/>task create · history · detail · live progress"]
    end

    subgraph WEB["Web (Docker)"]
        NGINX["Nginx · :8080<br/>static files + API proxy"]
    end

    subgraph API["Backend Layer — FastAPI · :8000"]
        MIDDLEWARE["TraceIDMiddleware<br/>(X-Trace-ID → ContextVars)<br/>trace_id · agent_name · execution_id · step_id"]
        ROUTERS["API Routers — /api/v1<br/>health · llm · plan · research · data<br/>orchestrator · history · stream · stats · retry"]
        CORE["Core Services<br/>config (pydantic-settings) · logging (colorlog)<br/>database (async SQLAlchemy)<br/>execution_repository · state_manager"]

        subgraph ORCH["Agent Orchestration — LangGraph StateGraph"]
            MASTER["Main Orchestrator Graph<br/>run_planner → check_max_steps →<br/>run_research → run_data? → run_synthesis<br/>re_plan → check_degradation"]
            PL_PLANNER["Planner sub-graph<br/>validate → generate → parse"]
            RS_RESEARCH["Research sub-graph<br/>per step: search → scrape → summarize"]
            DA_DATA["Data sub-graph<br/>analyze → codegen → execute → reflect"]
            SN_SYNTH["Synthesis sub-graph<br/>collect → generate → validate"]
        end

        subgraph TOOLS["Tools Layer — BaseTool registry"]
            TOOL_SEARCH["web_search<br/>DuckDuckGo (ddgs)"]
            TOOL_SCRAPE["web_scraper<br/>httpx + BeautifulSoup"]
            TOOL_PYTHON["python_executor<br/>sandboxed subprocess"]
            TOOL_SQL["sql_query<br/>read-only PostgreSQL"]
        end

        subgraph LLM_LAYER["LLM Layer — provider factory + registry"]
            LLM_IF["LLMProvider interface<br/>(generate · list_models)"]
            LLM_OLLAMA["OllamaProvider<br/>tenacity retry (3 × exp backoff)"]
            LLM_ECHO["EchoProvider<br/>(deterministic · tests)"]
        end

        subgraph OBS["Observability"]
            TRACE_WRAP["_TracedLLMProvider · _TracedTool<br/>persist llm_calls / tool_calls"]
            TLS_LOGS["Structured logs<br/>trace_id · agent_name · latency_ms"]
            METRICS["compute_and_upsert_metrics"]
        end
    end

    subgraph DATA_LAYER["Data Layer"]
        PG[("🗄️ PostgreSQL 15")]
        TAB_EXEC["executions"]
        TAB_STEPS["execution_steps"]
        TAB_LLM["llm_calls"]
        TAB_TOOL["tool_calls"]
        TAB_METRICS["execution_metrics_cache"]
        REDIS[("⚡ Redis 7")]
    end

    subgraph EXTERNAL["External Services"]
        EXT_OLLAMA["Ollama server · :11434"]
        EXT_DDG["DuckDuckGo"]
        EXT_WEB["Websites"]
    end

    %% Client flow
    USER --> BROWSER
    BROWSER -->|HTTP + SSE| NGINX
    NGINX -->|/api/v1 proxy| MIDDLEWARE --> ROUTERS

    %% Backend wiring
    ROUTERS --> CORE
    ROUTERS -->|POST /execute-task| MASTER
    CORE -.->|traces| TRACE_WRAP

    %% Orchestrator → sub-graphs
    MASTER --> PL_PLANNER
    MASTER --> RS_RESEARCH
    MASTER --> DA_DATA
    MASTER --> SN_SYNTH

    %% Agents → LLM
    PL_PLANNER --> LLM_IF
    RS_RESEARCH --> LLM_IF
    DA_DATA --> LLM_IF
    SN_SYNTH --> LLM_IF

    %% Agents → tools
    RS_RESEARCH --> TOOL_SEARCH
    RS_RESEARCH --> TOOL_SCRAPE
    DA_DATA --> TOOL_PYTHON
    DA_DATA --> TOOL_SQL

    %% Providers
    LLM_IF --> LLM_OLLAMA
    LLM_IF --> LLM_ECHO
    LLM_OLLAMA -->|http| EXT_OLLAMA

    %% Observability wiring
    TRACE_WRAP --> TAB_LLM
    TRACE_WRAP --> TAB_TOOL
    TRACE_WRAP --> TAB_STEPS

    %% Persistence
    CORE --> PG
    MASTER --> PG
    MASTER --> TAB_METRICS
    MASTER --> REDIS
    CORE --> REDIS

    %% External
    TOOL_SEARCH --> EXT_DDG
    TOOL_SCRAPE --> EXT_WEB

    classDef client fill:#61dafb,stroke:#333,color:#000
    classDef web fill:#4db6ac,stroke:#2c3e50,color:#fff
    classDef backend fill:#009688,stroke:#333,color:#fff
    classDef agent fill:#ff9800,stroke:#333,color:#fff
    classDef tool fill:#4caf50,stroke:#333,color:#fff
    classDef llm fill:#9c27b0,stroke:#333,color:#fff
    classDef data fill:#2196f3,stroke:#333,color:#fff
    classDef external fill:#f44336,stroke:#333,color:#fff
    classDef obs fill:#607d8b,stroke:#333,color:#fff

    class USER,BROWSER client
    class NGINX web
    class MIDDLEWARE,ROUTERS,CORE backend
    class MASTER,PL_PLANNER,RS_RESEARCH,DA_DATA,SN_SYNTH agent
    class TOOL_SEARCH,TOOL_SCRAPE,TOOL_PYTHON,TOOL_SQL tool
    class LLM_IF,LLM_OLLAMA,LLM_ECHO llm
    class PG,TAB_EXEC,TAB_STEPS,TAB_LLM,TAB_TOOL,TAB_METRICS,REDIS data
    class EXT_OLLAMA,EXT_DDG,EXT_WEB external
    class TRACE_WRAP,TLS_LOGS,METRICS obs
```

Note: the `TAB_*` tables, Redis, and the external services are the canonical deployments backing the components above.

### 1.1 API surface (OpenAPI at `/docs`)

All routes are under `/api/v1`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Redis + PostgreSQL liveness probes |
| `POST` | `/test/generate` | LLM provider smoke test |
| `GET` | `/test/models` | List models from the provider |
| `POST` | `/plan` | Run Planner sub-graph standalone |
| `POST` | `/research` | Run Research sub-graph standalone |
| `POST` | `/data` | Run Data sub-graph standalone |
| `POST` | `/execute-task` | Full pipeline: Planner → Research → (Data) → Synthesis |
| `POST` | `/task/{trace_id}/retry` | Re-execute a task's description |
| `GET` | `/tasks` | List executions (pagination, status filter, search) |
| `GET` | `/tasks/{trace_id}` | Detail: report, steps, LLM & tool calls |
| `GET` | `/tasks/{trace_id}/metrics` | Cached metrics for the execution |
| `GET` | `/tasks/{trace_id}/stream` | SSE — live progress events |
| `GET` | `/stats` | Aggregated stats (success rate, avg duration…) |

## 2. Orchestration

### 2.1 Orchestrator graph (LangGraph `StateGraph`)

Every agent node flows through a `check_max_steps` gate; errors go to `re_plan`, which asks the LLM for `retry | skip | abort` and is bounded by `check_degradation` (3 consecutive failures on the same agent → abort).

```mermaid
graph LR
    START(["POST /execute-task"]) --> PL["run_planner"]
    PL --> CHK1["check_max_steps"]
    CHK1 -->|ok| RE["run_research"]
    RE --> CHK2["check_max_steps"]
    CHK2 -->|plan needs data| DA["run_data"]
    CHK2 -->|no data needed| SY["run_synthesis"]
    DA --> CHK3["check_max_steps"]
    CHK3 --> SY
    SY --> END((END))
    CHK1 -->|error| RP["re_plan"]
    CHK2 -->|error| RP
    CHK3 -->|error| RP
    RP --> CD["check_degradation"]
    CD -->|retry/skip| PL
    CD -->|abort| ENDF
```

- **State contract** (`OrchestratorState`): `task_description`, `objective`, `plan`, `plan_steps`, `research_findings`, `data_results`, `report`, `error`, `current_agent`, `step_index`, `total_steps`, `max_steps`, `checkpoint_idx`, `consecutive_failures`, `last_failure_agent`, `trace_id`, `execution_id`, `last_step_latency_ms`.
- **Hard limits**: `MAX_TOTAL_STEPS = 50` and `DEGRADATION_THRESHOLD = 3` (`backend/app/core/orchestrator.py`). Exceeding steps → status `TIMEOUT`; too many consecutive failures → `FAILED`.
- **Checkpoints**: after each agent node the sanitized state is written to Redis (`orchestrator:{id}` via `state_manager.save_orchestrator_state`), TTL 1 h. `run_planner` also creates the `executions` row in PG and every node records a step.
- **Timeouts**: `/execute-task` wraps `graph.ainvoke()` in `asyncio.wait_for(…, 600)` → HTTP 504 on timeout.

### 2.2 Agent sub-graphs

| Agent | Nodes (edges) | Iteration / guard |
|---|---|---|
| Planner | `validate → generate (LLM) → parse (Pydantic Plan)` | stops on validation/parse error |
| Research | `parse_step → web_search → scrape (top 3 URLs) → synthesize_finding (LLM)` per step | loops until steps exhausted |
| Data | `analyze → generate_code → classify (python/sql/both) → execute (python/sql) → reflect_error` | max 3 retries |
| Synthesis | `collect_results → generate (LLM) → validate` | max 3 attempts |

The orchestrator decides whether to launch the Data agent via a keyword heuristic on the plan steps (`_check_if_data_needed`); the Data agent itself decides which tool(s) to run based on LLM classification of the generated code.

## 3. Execution sequence — `POST /execute-task`

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (React)
    participant API as FastAPI /execute-task
    participant ORC as Orchestrator graph
    participant P as Planner graph
    participant R as Research graph
    participant D as Data graph
    participant S as Synthesis graph
    participant L as LLM provider (Ollama/Echo)
    participant T as Tools
    participant PG as PostgreSQL
    participant RD as Redis

    C->>API: POST /api/v1/execute-task {task_description}
    API->>ORC: graph.ainvoke(state with trace_id)
    ORC->>PG: execution_repository.create_execution (running)
    ORC->>P: run_planner
    P->>L: LLM plan generation
    L-->>P: Plan JSON
    P->>ORC: objective + plan_steps
    ORC->>RD: save checkpoint (orchestrator:{id})
    ORC->>PG: record step (planner)

    loop each plan step
        ORC->>R: run_research
        R->>T: web_search(query, max_results=5)
        T-->>R: results
        R->>T: scrape top 3 URLs
        T-->>R: content ≤3000 chars
        R->>L: LLM finding summary
        L-->>R: summary
        R-->>ORC: findings[]
    end
    ORC->>RD: save checkpoint (orchestrator:{id})
    ORC->>PG: record step (research)

    alt plan needs data
        ORC->>D: run_data
        D->>L: analyze_task + generate_code + classify
        D->>T: python_executor / sql_query
        T-->>D: result or error
        Note over D: reflect_error retry loop ≤ 3
        D-->>ORC: data_results
        ORC->>PG: record step (data)
    else data not needed
        ORC-->>ORC: skip data
    end

    ORC->>S: run_synthesis
    S->>L: LLM report generation (validate ≤ 3)
    L-->>S: report
    S-->>ORC: report

    ORC->>PG: update_execution (completed, report, total_steps)
    ORC->>PG: compute_and_upsert_metrics
    ORC->>PG: record step (synthesis)
    API-->>C: 200 ExecuteTaskResponse { report, plan, findings, data_results }

    Note over C,PG: UI also subscribes via SSE
    C->>API: GET /api/v1/tasks/{trace_id}/stream (EventSource)
    loop until terminal status
        API-->>C: event("progress") {steps}
    end
    API-->>C: event("complete") {report, metrics}
    C->>C: close EventSource
```

**Failure path**: each agent node marks the execution `failed`, records a failed step and metrics, and propagates `error` in state → `re_plan` LLM decision (`retry`/`skip`/`abort`); `abort` or `check_degradation` ends the run (still persisted for history).

## 4. Tools layer

Interface: `BaseTool` (`name`, `description`, `execute(**kwargs) → ToolResult`, `input_schema()`). Tools are registered in a global registry (`register_tool`/`get_tool`) and wrapped with `_TracedTool` (persists `tool_calls`).

| Tool | Implementation | Security |
|---|---|---|
| `web_search` | `ddgs` (DuckDuckGo), default `max_results=5` | query validation |
| `web_scraper` | httpx + BeautifulSoup, `max_chars=3000`; strips scripts/nav/footers | 15s timeout, strict URL |
| `python_executor` | subprocess + tempfile + empty env + rlimits | sandboxed (below) |
| `sql_query` | SQLAlchemy `text()` against async engine | read-only policy (below) |

### 4.1 Python sandbox (`python_executor`)

- **Static (AST)**: allowlisted imports (`pandas`, `numpy`, `matplotlib`, `json`, `math`, `statistics`, …); blocks `exec`, `eval`, `compile`, `__import__`, `open`, `os.*`, `subprocess.*`.
- **Runtime**: `subprocess.run` with `env={}`, `timeout=30s`, Linux `setrlimit` memory 256 MB, CPU time = timeout, no core dumps; temp file removed in `finally`; control-char sanitization.

### 4.2 SQL read-only policy (`sql_query`)

`SELECT` / `WITH … SELECT` only; no `;` (multi-statement), no comments, no shell meta-commands; keyword blacklist (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `PG_SLEEP`, `COPY…FROM PROGRAM`, …).

## 5. LLM provider layer

- `LLMProvider` interface: `generate(prompt, system)`, `list_models()`.
- Factory `get_llm_provider()` reads `llm_provider` from config (`echo` is default, `ollama` for real runs); `register_provider()` extends the registry.
- `OllamaProvider`: HTTP (`/api/generate`, `/api/tags`) with `tenacity` retry — 3 attempts, exponential 2–10 s, only on `httpx` timeouts/network errors.
- `EchoProvider`: deterministic echo for tests/dev.
- All providers are wrapped in `_TracedLLMProvider` which writes `llm_calls` rows (prompt preview, estimated tokens `len//4`, latency, error).

## 6. Data model (PostgreSQL)

Tables created via SQLAlchemy metadata (`backend/scripts/init_db.py`):

```mermaid
erDiagram
    EXECUTIONS ||--o{ EXECUTION_STEPS : "has steps"
    EXECUTIONS ||--o{ LLM_CALLS : "records"
    EXECUTIONS ||--o{ TOOL_CALLS : "records"
    EXECUTIONS ||--o| EXECUTION_METRICS_CACHE : "metrics"

    EXECUTIONS {
        uuid id PK
        string trace_id UK "public identifier"
        text task_description
        text objective
        json plan
        status status "pending|running|completed|failed|timeout"
        int total_steps
        text error
        text report
        datetime created_at
        datetime started_at
        datetime completed_at
    }
    EXECUTION_STEPS {
        uuid id PK
        uuid execution_id FK
        string trace_id
        string agent_name "planner|research|data|synthesis|orchestrator"
        string step_type
        text input_summary
        text output_summary
        string status
        int latency_ms
    }
    LLM_CALLS {
        uuid id PK
        uuid execution_id FK
        uuid step_id FK "nullable"
        string trace_id
        string agent_name
        text system_prompt
        text user_prompt
        text response
        string model
        int latency_ms
        int estimated_tokens_input
        int estimated_tokens_output
    }
    TOOL_CALLS {
        uuid id PK
        uuid execution_id FK
        uuid step_id FK "nullable"
        string tool_name
        json input
        string output_preview
        string status
        int latency_ms
    }
    EXECUTION_METRICS_CACHE {
        uuid execution_id PK
        string trace_id UK
        int total_duration_ms
        int total_steps
        int total_llm_calls
        int total_tool_calls
        int total_tokens_input
        int total_tokens_output
        float estimated_cost_usd "0.0 — not implemented"
        float avg_step_latency_ms
        float avg_llm_latency_ms
        int error_count
    }
```

All reads/writes go through `execution_repository` (per-method `SessionLocal` sessions). Metrics are upserted (`on_conflict_do_update` on the PK) whenever the execution reaches a terminal state (`completed`/`failed`/`timeout`).

## 7. Observability

- **Trace ID**: `TraceIDMiddleware` reads `X-Trace-ID` (or generates one) and echoes it back in the response header; `ContextVar`s thread `trace_id`, `agent_name`, `execution_id`, `step_id` through async tasks.
- **Structured logs**: colorlog with those fields inline; `@trace_step` decorator reports agent latency (`last_step_latency_ms`).
- **Traced proxies**: every LLM call & tool call is persisted asynchronously (`asyncio.ensure_future`) — pipeline degrades gracefully if DB writes fail.
- **Metrics & stats**: `execution_metrics_cache` + `GET /stats`.

## 8. Redis usage

JSON snapshots with TTL 1 h under:

- `orchestrator:{id}` — full orchestrator state written after each agent node (`save_orchestrator_state`).
- `research:{id}` — `StateManager` exposes `save/get_research_state` for standalone research runs; not exercised by the current orchestration path.

`/health` performs `redis.ping()` and `SELECT 1` checks. **Write-only** checkpoints: no resume-from-checkpoint path exists (see §10).

## 9. Decision log & tradeoffs

| # | Area | Decision (chosen) | Why | Trade-offs / cost | Better-late alternatives |
|---|---|---|---|---|---|
| 1 | **Python sandbox** | Subprocess + AST allowlist + rlimits (256 MB, CPU, no core) + empty env + temp files | Zero infra, deterministic, fast, enough for a learning project | Not a containment boundary: escaped AST validation can reach host FS/network; no per-user quotas | Docker-per-run (volumes, GC), RestrictedPython, or OCI runtime with seccomp |
| 2 | **Live updates** | SSE (`sse-starlette` + `EventSource`) with 1s poll-and-push on change | Server→client only; auto-reconnect; nginx-friendly; no WebSocket state to manage | ≥1s latency; no client→server commands; still requires DB polling | WebSocket if bidirectional control (pause/cancel) or chat is needed |
| 3 | **Checkpoints** | Redis JSON snapshots (TTL 1h) | Reuses Redis, debuggable, zero new deps | Write-only today; no resume after restart/crash; snapshot cost on large states | LangGraph `checkpointer` (PostgresSaver) for durable replay + resume |
| 4 | **Execution model** | Synchronous in-request `graph.ainvoke` (600 s timeout) | Simplest model; easy debugging/test; single Docker process | Blocks a uvicorn worker; no horizontal scaling; client needs a long fetch timeout | Background workers (Celery/ARQ/RQ) + status polling |
| 5 | **LLM abstraction** | Interface + factory + registry (`echo` default) | Provider-agnostic; deterministic tests; config-driven | No streaming support; only Ollama/Echo shipped | Streaming `generate_stream`; OpenAI/Anthropic adapters |
| 6 | **LLM retries** | `tenacity` 3 attempts, exp backoff 2–10 s on network/timeout only | Bounded latency; avoids re-running prompts on persistent failures | HTTP 5xx not retried; no circuit breaker | Status-code-based retries with budgets |
| 7 | **SQL safety** | Static policy (SELECT/WITH + keyword blacklist) | Zero infra; enough for the demo | Regex ≠ parser; blacklist bypass risk; app DB user privileges | Dedicated read-only role + `pg_query`/sqlglot validation |
| 8 | **Observability** | ContextVars + traced proxies + full persistence (prompts, tokens) in PG | Complete audit trail w/o external services; easy SQL joins | Stores sensitive prompt text; DB-bound writes are fire-and-forget | OpenTelemetry export; run sinks; PII redaction |
| 9 | **Metrics** | Materialized `execution_metrics_cache` upsert on transitions | `/metrics`, `/stats` are instant | Stale between transitions; `estimated_cost_usd` = 0.0 | Streams/prom aggregates to a time series |
| 10 | **UI progress** | Hybrid: synchronous execute fetch + SSE detail page | Both worlds: simple create, live progress on detail | Progress only visible on detail page; execute itself is 10-min fetch | Full WS-driven execute page; incremental report streaming |
| 11 | **Standalone agent endpoints** | `/plan`, `/research`, `/data` reuse sub-graphs | Demos, isolated debugging, tests | Those runs aren't persisted/traced | Unify behind a single facade with an execution id |

## 10. Known limitations & next steps

- Redis checkpoints are write-only — no in-flight resume.
- `estimated_cost_usd` is hardcoded `0.0`.
- SQL safety is heuristic; DB role isn't least-privilege.
- Python sandbox is process-level, not a container boundary (tradeoff #1).
- `/task/{trace_id}/retry` starts a new execution instead of reusing the original trace.
- No auth, no multi-tenancy, CORS `*`.
- No token streaming from the LLM layer (only full responses).
- `.env` path resolution requires running from `backend/` (see AGENTS.md quirks).
