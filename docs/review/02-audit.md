# Deep technical audit — Atlas Research System

**Repository:** `atlas_research_system` · **Date:** 2026-10-15
**Scope:** per-module technical audit (no code modified). Complements `docs/review/01-diagnostico.md`.
**Convention:** each finding includes *(approximate file:line)* + severity (**critical** / **important** / **minor**) + fix effort (**quick** / **moderate** / **requires refactor**).

---

## 0. Real tool results

Environment: Python 3.13, venv at `.venv/`. For pytest I brought up `postgres` + `redis` with `docker compose up -d postgres redis`, generated the schema with `scripts/init_db.py` and ran the suite with `DATABASE_URL` pointing at `localhost` and `LLM_PROVIDER=echo` (the `.env` files point at the container hostnames `postgres`/`redis`, see §6). The containers were stopped when done.

### Backend

| Command | Real result |
|---|---|
| `ruff check app/` | **PASS** — `All checks passed!` (exit 0) |
| `ruff format --check app/` | **FAIL** (exit 1) — 3 files would be reformatted: `core/database.py`, `core/tracing.py`, `schemas/base.py` |
| `mypy app/` | **PASS** — `Success: no issues found in 59 source files` (exit 0), with `ignore_missing_imports=true` and no strict mode (see §9) |
| `pytest tests/ --cov=app` | **PASS** — `229 passed in 4.00s`; coverage **app-only: 89%** (2092 stmts, 236 miss) |

Coverage by module (the gaps matter):

```
core/llm/ollama.py                 32%   (0 real calls to Ollama)
core/llm/retry.py                  33%   (tenacity config never exercised)
api/routes/retry.py                42%   (retry handler uncovered)
api/routes/data.py                 50%
core/redis_client.py               57%
core/execution_repository.py       71%   (compute_and_upsert_metrics 176-256 UNCOVERED)
core/agents/data.py                93%
```

The `--cov=.` in `pytest.ini` (addopts) also adds `tests/` and `scripts/`, inflating the reported total to **88.64%**; CI uses `--cov=app` but still drags the addopts along. **The most complex method in the repo (`compute_and_upsert_metrics`, an `ON CONFLICT` upsert) and 100% of the listing/stats queries never run in any test** (all mocked, see §9).

### Frontend

| Command | Real result |
|---|---|
| `npx oxlint` | **PASS with 1 warning** — `react(only-export-components)` in `ToastProvider.tsx:74` |
| `npx tsc -b` | **PASS** (exit 0) |
| `npx vitest run` | **PASS** — `5 test files, 20 tests passed` (1.23 s) |

### Docker (real image size)

| Image | Size | Note |
|---|---|---|
| `atlas_research_system-backend` | **747 MB** | single-stage, includes dev-deps (mypy/ruff/pytest) and pandas+numpy |
| `atlas_research_system-frontend` | **103 MB** | correct multi-stage (node build → nginx) |

---

## 1. Orchestration and state

### 1.1 Graph termination — **critical / moderate**

The graph **does not guarantee termination on its own**; in one case it depends solely on the HTTP timeout:

- `re_plan` with a `skip` decision sets `consecutive_failures: 0` (`orchestrator.py:686-692`) and `_next_agent("synthesis")` returns `"synthesis"` (`orchestrator.py:727-729`), which `route_after_replan` maps back to `run_synthesis` (`:739-745`).
- If Synthesis fails and the re-plan LLM repeatedly answers `skip` (a plausible case: a weak or deterministic provider), the cycle `synthesis → re_plan → check_degradation → synthesis` **repeats indefinitely without incrementing `total_steps`** (the synthesis failure returns before the increment, `orchestrator.py:576-580`), so `check_max_steps` never fires and `check_degradation` is reset on every `skip`.
- The only real brake is `asyncio.wait_for(..., 600)` in the route (`routes/orchestrator.py:35`). That is, the `MAX_TOTAL_STEPS=50` "hard limit" does not protect the re-planning loop.

### 1.2 Timeout leaves the execution stuck in `running` — **critical / quick**

When `wait_for(600)` expires, the route raises `HTTPException(504)` (`routes/orchestrator.py:36-39`, identical in `routes/retry.py:40-43`) **without marking the execution as `failed`/`timeout` in the DB or cleaning up the Redis checkpoint**. The row stays `running` forever:

- `GET /tasks` lists it as active forever.
- The SSE generator (`routes/stream.py:52-60`) runs `while True` and only ends if the status is terminal → **the stream never emits `complete`; the client reconnects indefinitely**.
- There is no global exception handler (`main.py` registers no handlers) that performs cleanup on cancellation.

### 1.3 Typed but unvalidated state; dead fields — **important / quick**

- `OrchestratorState` and the sub-states are `TypedDict`s (`orchestrator.py:24-42`) with no runtime validation; partial dicts are passed on each `ainvoke` (e.g. without `trace_id` in the subgraphs) and LangGraph does not validate required keys.
- `step_index` and `max_steps` are declared and passed from the route (`routes/orchestrator.py:28-31`), but `check_max_steps` uses the module constant `MAX_TOTAL_STEPS`, not `state["max_steps"]` (`orchestrator.py:785`). Both fields are inert.
- `data_results: list | None` is declared in the state, but `run_data` stores a **dict** (`orchestrator.py:454` ← `agents/data.py:144-148`).

### 1.4 Risky state mutations — **minor / moderate**

- `_sanitize_for_json` recursively converts non-serializable objects to `str()` (`orchestrator.py:66-97`), but **`with_checkpoint` stores `dict(result)` WITHOUT sanitizing** (`:100-109`). If a node produces a non-JSON-serializable object (e.g. a `datetime` in a finding), `save_orchestrator_state → json.dumps` throws and, unlike `save_checkpoint` (which catches the exception, `:57-61`), the wrapper **does not catch** → the node fails because of an observability problem. Two checkpoint paths with different robustness.
- The general pattern `return {**state, ...}` (shallow copy) is safe against in-place mutation, but the accumulators (`findings = state.get("findings", []) + [...]`) correctly create new lists; however `_check_if_data_needed`/`_build_data_context` re-read sub-keys with defensive `.get` due to loose typing, a symptom of untyped state.

### 1.5 Checkpoints — **important / moderate**

- The checkpoint key is a new `uuid4` (`checkpoint_idx`, `orchestrator.py:52`) **unrelated to `trace_id` or `execution_id`**, so there is no way to recover the state of a specific execution from Redis (the roadmap's "resume" would need another key scheme).
- Write-only confirmed: there is no `get_orchestrator_state` (`state_manager.py:16-18` only exposes `save`).
- `save_checkpoint` runs in `run_planner` and `with_checkpoint` in research/data/synthesis → two coexisting patterns (see diagnostic §B1).

### 1.6 Dead routers — **minor / quick**

- The `"error"` branches of `route_from_planner/research/data` (`orchestrator.py:607-627`) are unreachable: `route_after_check` intercepts the `error` first and returns `"re_plan"`/`"end"` (`:809-823`).
- The `"error"` key of the `add_conditional_edges` dict (`:854`) is never returned.
- `build_orchestrator_graph()` and the `build_*_graph()` functions are compiled on every request/node, not once (negligible overhead today, but avoidable with caching).

---

## 2. Agents and prompts

### 2.1 Fragile parsing of LLM outputs (no structured output) — **important / moderate**

- **Planner**: direct `json.loads(state["llm_response"])` (`agents/planner.py:74`), without stripping ```json fences. If the model wraps its response in markdown, the whole pipeline fails; **there is no retry or repair** in the Planner (unlike Data/Synthesis).
- **re_plan**: `json.loads(response.strip())` inline in the orchestrator (`orchestrator.py:668-670`); on any noise it falls back to `abort` (a "safe" behavior but one that degrades all error recovery).
- **Data** and **classify** do use `_strip_markdown_code` (`agents/data.py:27-33,92`) → **a different parsing strategy per agent**.
- Neither the providers' native structured output (Ollama supports `format: json`; LangChain's `PydanticOutputParser` is available via the `langchain-core` dependency but is unused) nor `response_format` is used. Pydantic validation exists (`Plan`) but **only reacts to an already-parsed JSON**; there is no semantic validation that 3–7 steps are respected or that `step_type` is coherent with the action.

### 2.2 Agent logic coupled to infrastructure — **important / requires refactor**

- Agent nodes do direct I/O against the DB (`run_planner` calls `execution_repository.create_execution/update_execution`, `orchestrator.py:161-255`), mixing the graph with persistence. The business logic (data-needed decision, re-planning) lives in the same file as the persistence calls.
- The orchestrator knows subgraph implementation details (return key names like `execution_result`, `findings`) with no shared contract/type → coupling by string convention.
- `_check_if_data_needed` is a keyword heuristic (`orchestrator.py:460-478`) that **should be the Planner's decision** (`step_type == "analysis"`); it also has a bug: it evaluates `step.get("action") or step.get("step_type")` (`:475`), and since `action` always exists, **`step_type` is never consulted**.

### 2.3 Versionable, maintainable prompts — **important / moderate**

- The registry (`core/prompts/`) is a good base (classes with `version`/`description`), but the **re-planning prompt is hardcoded inline** (`orchestrator.py:653-666`) and stays outside the versioning system.
- `PromptTemplate.template` is declared `@property @abstractmethod` but every subclass overrides it as a class attribute → the ABC contract is not really honored (fragile if someone defines a real property).
- Copy-paste descriptions: `SynthesisSystemPrompt.description` and `SynthesisUserPrompt.description` say *"for data analysis agent"* (`prompts/synthesis.py:20,34`).
- The list of allowed libraries is duplicated in the CodeGen prompt (`prompts/data.py:43-45`) and in `ALLOWED_IMPORTS` (`tools/python_executor.py:8-24`) → guaranteed drift.

---

## 3. Resilience

### 3.1 Cancellation / timeout does not propagate state — **critical / quick** (see §1.2)

### 3.2 Retries and LLM provider outage — **important / moderate**

- `retry_config` (`core/llm/retry.py:48-61`) retries **only** `httpx.TimeoutException|NetworkError`; it does **not** retry HTTP 5xx (`response.raise_for_status()` in `ollama.py:37` throws `HTTPStatusError`, outside the retry) — acknowledged in the decision log.
- There is no circuit breaker and no concurrency limit toward Ollama; if Ollama is down, every agent fails → re_plan → retry, multiplying the load.
- The factory **creates a new provider instance (and a new wrapper) on every `get_llm_provider()`** (`llm/factory.py:18-29`), and `httpx.AsyncClient` is instantiated **per call** (`ollama.py:25,49`) → no HTTP connection pooling.
- The tenacity retry is not exercised in tests (`retry.py` 33% coverage); there is no test for a downed provider.

### 3.3 Idempotency — **important / moderate**

- `POST /execute-task` does not accept an idempotency key; a client's network retry creates a new execution (documented for `/retry`, but it applies to the main POST).
- The `UNIQUE(trace_id)` on `executions` is the only guard, and it is precisely what collides with the Planner retry (`orchestrator.py:161-165` outside the `try`) → uncontrolled `IntegrityError` (critical bug already reported in `01-diagnostico.md` §B10.4).

### 3.4 Partial results — **important / moderate**

- There is no graceful degradation: if Research fails after 2 of 7 steps, `re_plan` can `skip` and Synthesis receives only the accumulated findings… but `run_research` **does not propagate** the partial findings when it throws/returns an error (`orchestrator.py:308-334` returns the state without `research_findings`), so the work done is lost and the final report can come out without evidence without being marked as degraded.

### 3.5 Backoff / jitter — **minor / quick**

`wait_exponential(multiplier=1, min=2, max=10)` without `jitter` (`retry.py:50`); no thundering herd with a single provider, but it is the expected practice.

### 3.6 No BackgroundTasks / real cancellation — **minor / requires refactor**

`grep BackgroundTasks` = 0 results; there is no cancellation endpoint or exposed `task.cancel()`. Long tasks are cancelled only by dropping the connection (and with the problem of §1.2).

---

## 4. Data layer

### 4.1 No schema migrations — **important / requires refactor**

`init_db()` uses `Base.metadata.create_all` (`core/database.py:24-27`); **there is no Alembic or any migration system** (grep `alembic` = 0). Any column change requires recreating/altering by hand; the orphan `tasks` table is created on every startup. Already declared as a limitation in the roadmap, but it is a visible gap for a backend AI Engineer role.

### 4.2 Pooling, `pool_pre_ping`, SSL — **important / quick**

- `create_async_engine(settings.database_url, echo=settings.debug)` (`database.py:9`) uses the pool defaults (size 5 + overflow 10) without `pool_size`, `max_overflow`, `pool_pre_ping` or `pool_recycle`. In a long-lived container, connections killed by Postgres restarts are not recycled; there is no `pre_ping`.
- **There are no SSL/`connect_args` parameters** for asyncpg → it does not support `sslmode=require`/TLS without touching code; there is no configurable `command_timeout` or `statement_cache_size`.
- `SessionLocal` uses `expire_on_commit=False` (reasonable), but **every repository method opens and closes its own session** (`execution_repository.py`) → a typical execution opens and closes dozens of connections; there is no per-request session or transaction spanning several writes (e.g. `update_execution` + `add_step` are not atomic).

### 4.3 SQL injection — **minor / quick** (mostly OK)

- All queries in the app use ORM/param binding; `list_executions` uses `.like(f"%{q}%")` with a bound parameter (`execution_repository.py:133`) — safe against SQLi, although the user's `%`/`_` are not escaped (pattern injection, not SQL injection).
- The tool exposed to the LLM uses `text(query)` with static validation (`tools/sql_query.py:35,51-112`): regex blacklist (bypassable: `SELECT ... FROM pg_catalog.pg_tables` is valid and allowed; `WITH x AS (DELETE ...) SELECT` falls because DELETE is blacklisted, but the heuristic is not a parser), and **it runs with the same user/DB as the application** without a real read-only role.

### 4.4 Indexes — **minor / quick**

- Good: `trace_id` unique+index, `status` index, indexes by `execution_id` on steps/llm/tool.
- Missing index on `executions.created_at` even though `list_executions` orders by `created_at DESC` (`execution_repository.py:137`) → sort/seq scan at scale. `ExecutionStep` has no composite `(execution_id, created_at)` index for `get_steps`.

### 4.5 Model / integrity — **minor / moderate**

- `execution_steps.trace_id`, `llm_calls.trace_id`, `tool_calls.trace_id` duplicate `executions.trace_id` without an FK → risk of inconsistency (denormalization).
- `Execution.started_at` has `default=now` **and** is assigned explicitly in `create_execution` (`execution.py:44`, `execution_repository.py:34`).
- `plan` is `JSON` with no shape validation in the DB; `LLMCall.system_prompt/user_prompt/response` store the full prompt (risk of sensitive data, see §8).

---

## 5. API (FastAPI)

### 5.1 DB dependency injection is dead code — **minor / quick**

`get_db()` (`core/database.py:19-21`) is used by **no** router (grep = only the definition); handlers open sessions through the repository. FastAPI's DI for the DB is implemented and unused.

### 5.2 Inconsistent error scheme — **important / moderate**

- `ErrorResponse` exists (`schemas/base.py:25-37`) but is **used nowhere**; errors are returned as `HTTPException(detail=str)` (format `{"detail": ...}`) and, in the case of `/execute-task`, as **200 with a populated `error` field** (`schemas/orchestrator.py:11-19`, `routes/orchestrator.py:41-50`). Three error conventions coexist: the `BaseResponse` envelope, `{"detail": …}`, and 200-with-error.
- `routes/research.py:19` names the `/research` handler `create_plan` (copy-paste), visible in OpenAPI.

### 5.3 Blocking calls inside async endpoints — **important / moderate**

- `web_search` runs **synchronous** `DDGS()` (network) inside an async node (`tools/web_search.py:28-34`).
- `python_executor` runs **synchronous** `subprocess.run` for up to 30 s (`tools/python_executor.py:140-147`).
- Both block the uvicorn event loop: during an execution, **the SSE endpoint can freeze and `/health` does not respond**. There is no offloading to a threadpool.

### 5.4 Long tasks: no background, no dedicated polling, SSE coupled to the DB — **important / requires refactor**

- Current pattern: `graph.ainvoke` inside the HTTP request (up to 600 s) + SSE that **polls the DB every second** (`routes/stream.py:52-60`). The SSE does not receive events from the graph: it depends on the pipeline writing rows (accidental complexity). With the bug of §1.2, the stream never closes.
- There are no `BackgroundTasks`/queue; an execution consumes a uvicorn worker for minutes → no horizontal scaling.

### 5.5 Auth / rate limiting / CORS — **important / moderate (auth) · minor (rate limit)**

- **No authentication** on any endpoint (including `/test/generate`, `/test/models` which burn LLM compute, and `/execute-task` which runs sandbox code). Documented in §10 but a finding relevant to a portfolio.
- **No rate limiting** or concurrency limit; `/execute-task` is a cost amplifier.
- CORS `allow_origins=["*"]` **with** `allow_credentials=True` (`main.py:31-37`) — an invalid combination per the spec (the browser rejects it with credentials).

### 5.6 Timeouts and exception handling in routes — **important / quick**

- `except TimeoutError` in `/plan`, `/test/generate`, `/test/models` **with no `wait_for`** → dead except (`routes/plan.py:27-29`, `routes/llm.py:24-27,42-45`). Ollama throws `httpx.TimeoutException`, which is not `TimeoutError` → a slow provider produces an uncontrolled 500.
- Inconsistent timeouts: data 180 s, research 600 s, plan none.
- `routes/retry.py:20` does `return HTTPException(...)` (not `raise`) → 200 with body `{}`.

---

## 6. Configuration and secrets

### 6.1 Centralized settings layer — **strength**

`config.py` with `pydantic-settings` + `lru_cache` is correct and centralizes the environment. `.env.example` covers **all** `Settings` fields (verified field by field), including `TIMEZONE`.

### 6.2 Secrets — **important / quick**

- There are no hardcoded secrets in the source (clean grep).
- `.env` is in `.gitignore` (correct) and is not tracked.
- **Risk**: the Postgres password lives in plain text in `.env` and is injected into `docker-compose`; `docker-compose.yml` exposes `5432` and `6379` to the host without auth (Redis without a password). Acceptable locally, but there is no secret separation for a deployment and no Docker secrets.

### 6.3 Environment parity and scattered hardcoded values — **important / moderate**

- `.env.example` sets `REDIS_URL=redis://redis:6379` (container hostname) while the README documents a local flow with `uvicorn` on the host — **`.env.example` does not work as-is outside compose** (same problem with `DATABASE_URL=...@postgres:...`). For local tests I had to override both to `localhost`.
- `.env.example` uses `llm_provider` in lowercase while the rest are uppercase (works due to case-insensitivity, but it is inconsistent).
- Behavior constants scattered through the code instead of in `Settings`: timeouts `600.0`/`180.0`, TTL `3600`, `MAX_ITERATIONS=3`, `MAX_TOTAL_STEPS=50`, `DEGRADATION_THRESHOLD=3`, sandbox limits (`256 MB`, `30 s`), `max_results=5`, `max_chars=3000/5000`. None of this is configurable via the environment.
- `debug=True` is the default of the `Settings` dataclass (`config.py:23`) even though the real `.env` sets `False`; the safe default should be `False`.

---

## 7. Observability

### 7.1 Logger misattributed — **important / quick**

`logger = logging.getLogger(__name__)` is defined in `core/logging.py:71`, and all modules import it (`from app.core.logging import logger`) → the logger name is always `app.core.logging` and, with the format `%(module)s %(funcName)s` (`logging.py:49-51`), **all logs report `logging` as the emitting module**, no matter who logs. The log "structure" promised in the README degrades exactly in the field that most helps debugging.

### 7.2 Logs not machine-structured — **minor / moderate**

The README says "structured logs"; in reality it is text with colorlog + `trace_id`/`agent_name` interpolated into the format. There is no JSON output or exporter (OTel, structlog). The `extra={...}` from `trace_step` (`logging.py:92`) is passed but **no formatter renders it**, so `latency_ms` does not appear in the structured log, only in the message.

### 7.3 Tracing — **partial strength / important (gaps)**

- `TraceIDMiddleware` propagates `X-Trace-ID` to ContextVars and to the response (`core/middleware.py`) — good.
- **Gap 1**: the client's `X-Trace-ID` header is used **without validation** → log forging (see §8.4).
- **Gap 2**: in the writing of `llm_calls`/`tool_calls` via `asyncio.ensure_future` (`tracing.py:85,198`), if the request is cancelled by timeout (§1.2) the pending writes can be silently lost and **there is no reference to the tasks** (risk of garbage collection and of losing events).
- **Gap 3**: `LLMCall.model` is always stored as `None` (`tracing.py:96`) — the actual model used is not recorded, even though `OllamaProvider` knows it.

### 7.4 Token/latency/cost metrics — **minor / quick**

`estimated_tokens = len//4` (heuristic, documented) and `estimated_cost_usd=0.0` fixed (`execution_repository.py:228,243`). Per-agent latency is computed (`@trace_step`) but **is not reliably persisted in `llm_calls`/`tool_calls`** when there is cancellation (7.3). There is no Prometheus endpoint or time series.

---

## 8. Security

### 8.1 Indirect prompt injection from external content — **critical / requires refactor**

The Research agent downloads arbitrary web pages and **injects the scraped content directly into the LLM prompt without delimiting it or instructing the model to ignore it as instructions** (`agents/research.py:117-127`, `Content: {content}` on line 122; then it is formatted into the prompt at `:129-138`), and Synthesis embeds the findings in its prompt (`agents/synthesis.py:48-59`). An attacker who controls/positions a page in the search results can:
1. Inject instructions that alter the summaries, and
2. Push the system to emit controlled URLs/actions.

There is no prompt-injection defense (delimiters, marking untrusted content, defensive system instructions) and this vector does not appear in the decision log's threat model (only sandbox escape is discussed).

### 8.2 SSRF in `web_scraper` — **important / moderate**

`WebScraperTool.execute` does `client.get(url, follow_redirects=True)` **without validating scheme or host** (`tools/web_scraper.py:22-33`). Although the README/ARCHITECTURE describe it as *"strict URL"*, **no such validation exists**: URLs to `http://169.254.169.254/...` (cloud metadata), `http://localhost:...` or private ranges would still be followed, including redirects. There is no domain allowlist or blocking of private IPs. Classic SSRF triggered by content the LLM/plan chooses.

### 8.3 Python sandbox — documented escapes, but confirmed — **important / requires refactor**

The AST allowlist (`tools/python_executor.py:72-106`) blocks `open`/`os`/`subprocess`, but **the allowed libraries evade the control**: `pd.read_csv("http://…")`, `pd.read_csv("/etc/passwd")` or `numpy.load` do not go through the AST's `open()`. In addition, `env={}` (`:145`) prevents `matplotlib`/`pandas` from finding `HOME`/`MPLCONFIGDIR`, so the Data agent using matplotlib (allowed in the prompt) will fail at runtime. The decision log acknowledges it is not a containment boundary, but the report should list it as a security finding, not just a design one.

### 8.4 Input validation and log forging — **minor / quick**

- Pydantic validates lengths (`min_length`, `max_length`), which is good.
- `X-Trace-ID` is copied into logs without sanitizing (`middleware.py:11`) → a value with newlines can forge log entries.
- Agent error messages are returned to the client in `ExecuteTaskResponse.error` (`routes/orchestrator.py:47`) and include low-level `str(exc)` (can leak internal/DB details).

---

## 9. Testing and quality

### 9.1 Tests pass, but they are mostly mock-based — **important / requires refactor**

- **229 tests in 4 s** with **233 uses of `patch`/`AsyncMock`/`MagicMock`** (`test_api.py`: 57, `test_orchestrator.py`: 40…). The speed and the coverage gaps confirm that much of the real integration is not exercised.
- `compute_and_upsert_metrics` (the most delicate SQL in the repo, with `ON CONFLICT`) has **0% coverage** (`execution_repository.py:176-256`); `get_stats`/`list_executions`/`get_metrics` are not run either. The `UNIQUE` on `trace_id`, which does blow up in production (§3.3), has no test.
- `conftest.py` defines `db_session` and an autouse `reset_db` fixture that **resets nothing** (it only `yield`s): the tests that do touch the DB share state across runs.

### 9.2 LLM mocking — **acceptable / quick**

`LLM_PROVIDER=echo` (deterministic provider) is a good base decision (documented). But **there is no test with an Ollama double** (`ollama.py` 32%, `retry.py` 33%): neither the retry with backoff, nor a 5xx, nor a network timeout, nor the parsing of Ollama's response is tested.

### 9.3 No output quality evaluation — **important / requires refactor**

There is no type of evaluation of the quality of the agents' outputs (golden datasets, asserts on the structure/coverage of the plan, report quality, groundedness of findings). For an AI Engineer portfolio, **the total absence of evals is a central gap**: there is no way to demonstrate that the system produces good answers beyond "it does not throw an exception". `_check_if_data_needed` and the routing have no end-to-end behavior tests with realistic cases.

### 9.4 Coverage and threshold — **important / quick**

`pytest.ini` sets `--cov-fail-under=75` but **measures `--cov=.`** (includes `tests/` and `scripts/`, which inflate the number); CI adds `--cov=app` without removing the addopts. The result (88.64%) is misleading versus the real app-only figure (89% here, but with the gaps already cited). `scripts/generate_agent_docs.py` (217 stmts) is 0% covered and gets dragged into the computation.

### 9.5 CI: does not run types or format; partial lint — **important / quick**

`.github/workflows/ci.yml` runs **only** `ruff check backend/app/` and pytest; it **does not run `ruff format --check`** (that is why the 3 files with broken format go unnoticed, see §0), **does not run mypy** (despite configuring it in `pyproject.toml` and pre-commit), and **does not run the frontend's tests/build** (even though the week-10 development log claims a QA workflow existed). `tsc`, `oxlint` and `vitest` run only if someone launches them by hand.

### 9.6 Static quality: permissive mypy — **minor / moderate**

`mypy` passes, but with `ignore_missing_imports=true` and no `strict`/`disallow_untyped_defs`; it emits `annotation-unchecked` for `redis_client.py:11`. Given the portfolio goal, a `strict` (or at least `check_untyped_defs`) would make the typing signal much stronger. There are no abusive `type: ignore` or `noqa` (only 3, all justified) — a point in its favor.

---

## 10. Docker and deployment

### 10.1 Large backend image with dev-deps — **important / moderate**

- **747 MB** real. Cause: single-stage `python:3.13-slim` + `pip install -r requirements.txt` where `requirements.txt` **includes mypy, ruff, pytest, pytest-cov, pre-commit** (because they are in `[project].dependencies`, not in a dev group). Plus pandas+numpy (needed by the sandbox, but heavy).
- There is no multi-stage for the backend (the frontend does have it, 103 MB).
- `CMD [..., "--reload"]` (`backend/Dockerfile:10`) **serves with the development autoreload**; in the README's "deployment" image.

### 10.2 No non-root user or healthchecks — **important / quick**

- The backend runs as **root** (there is no `USER`); the nginx frontend does run as root (nginx default, it does not use `nginxinc/nginx-unprivileged`).
- **There is no `HEALTHCHECK`** in any Dockerfile, and `docker-compose.yml` declares no healthchecks or `depends_on: condition: service_healthy`. `backend` depends on `postgres` without waiting for readiness → on a cold start the first connection can fail (partially mitigated because connections are lazy).
- `redis`/`postgres` are published to the host unnecessarily and without auth (Redis), exposing surfaces in naive deployments.

### 10.3 Compose ↔ production parity — **important / moderate**

`docker-compose.yml` mounts `./backend/app:/app/app` (code bind-mount) and uses `--reload`: it is a **development** configuration, but the README presents it as the deployment path ("Run with Docker Compose"). There is no `docker-compose.prod.yml` or separate variables; `DEBUG=False` in the local `.env` helps, but the compose default behavior is dev. `OLLAMA_BASE_URL` is fixed to `host.docker.internal` in the compose (correct for the host) while `ollama_base_url` in `.env` points at another IP — two sources.

### 10.4 Dependency management — **important / quick**

- Correct source of truth (`pyproject.toml` + `uv.lock`, `requirements.txt` generated and synced), but **there is no dev/prod separation** (`[dependency-groups]`/extras) → dragged into the image.
- Pre-commit out of sync with pyproject: mypy hook `v1.15.0` vs `mypy>=2.3.0`; ruff hook `v0.11.0` vs `ruff>=0.15.21` (`.pre-commit-config.yaml` vs `pyproject.toml`).

---

## 11. Prioritized summary

### Critical (they block or severely degrade the system at runtime)

1. **Timeout leaves the execution `running` forever** (no terminal status, no cleanup, SSE never closes) — `routes/orchestrator.py:36-39`, `routes/retry.py:40-43`, `routes/stream.py:52-60`. *(quick)*
2. **Unbounded re-planning cycle** (`skip` on `synthesis` resets degradation and does not add to `total_steps`) — `orchestrator.py:676-692,727-729,739-745`. *(moderate)*
3. **Indirect prompt injection** from scraped content, with no delimiting or threat model — `agents/research.py:117-138`, `agents/synthesis.py:48-59`. *(requires refactor)*
4. **`IntegrityError` when retrying the Planner** (bug carried over from the diagnostic) — `orchestrator.py:161-165`. *(quick)*

### Important

5. Fragile LLM parsing with no structured output or retry in Planner/re_plan — `agents/planner.py:74`, `orchestrator.py:668-670`. *(moderate)*
6. Event-loop blocking by sync tools — `tools/web_search.py:28-34`, `tools/python_executor.py:140-147`. *(moderate)*
7. SSRF with no URL validation in the scraper (docs call it "strict URL" but it is not) — `tools/web_scraper.py:22-33`. *(moderate)*
8. No auth or rate limiting; `/execute-task` runs code and burns LLM — `main.py`, `routes/*`. *(moderate)*
9. No schema migrations — `core/database.py:24-27`. *(requires refactor)*
10. asyncpg pool without `pool_pre_ping`/`pool_recycle`/SSL/timeouts — `database.py:9`. *(quick)*
11. Logger misattributed across the whole system; `LLMCall.model` always `None`; fire-and-forget writes without references — `logging.py:71`, `tracing.py:85,96,198`. *(quick)*
12. CI runs neither mypy nor format nor frontend; coverage threshold inflated by `--cov=.` — `.github/workflows/ci.yml`, `pytest.ini`. *(quick)*
13. Backend image 747 MB with dev-deps, root, `--reload`, no healthchecks — `backend/Dockerfile`, `docker-compose.yml`. *(moderate)*
14. No agent output quality evals; real integration (upsert/UNIQUE) untested — `backend/tests/`. *(requires refactor)*
15. `.env.example` is not functional for the documented local flow (compose hostnames) — `.env.example`. *(quick)*
16. Inconsistent error scheme and dead `ErrorResponse`; dead `get_db` — `schemas/base.py:25`, `database.py:19`. *(moderate)*

### Minor

17. `ruff format --check` fails on 3 files (`database.py`, `tracing.py`, `schemas/base.py`). *(quick)*
18. Behavior constants outside `Settings` (timeouts, TTL, limits). *(moderate)*
19. Missing index on `executions.created_at`; denormalized `trace_id` without FK. *(quick)*
20. Dead routers and branches (`route_from_*`, `"error"` key); per-request graph recompilation. *(quick)*
21. Backoff without jitter; no circuit breaker; `httpx.AsyncClient` per call. *(moderate)*
22. `_check_if_data_needed` ignores `step_type` due to a short-circuited `or`. *(quick)*
23. CORS `*` + `allow_credentials=True` (invalid). *(quick)*
24. Unsanitized `X-Trace-ID` (log forging); `str(exc)` sent to the client. *(quick)*
25. Inconsistent standalone timeouts and dead `except TimeoutError` in `/plan` and `/test/*`. *(quick)*

### Verified strengths (to balance the report)

- Green, fast suite (229 backend + 20 frontend), error-free typing with mypy, clean lint except for format.
- Centralized configuration and complete `.env.example`; `echo` provider for deterministic tests; clear layering; tests of tools/sandbox with security cases.
- Architecture documentation and decision log aligned and honest about limitations.

**Note on workspace context:** even though the previous commands were run with the project's working directory, there are also images from another unrelated project (`atlas_rag_system-*`) on the system; the sizes reported above correspond only to `atlas_research_system-backend`/`-frontend`.
