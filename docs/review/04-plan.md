# Action plan — Getting Atlas Research System ready as a portfolio piece

**Based on:** `docs/review/01-diagnostico.md`, `02-auditoria.md`, `03-vision-reclutador.md`
**Goal:** that a recruiter/engineer who opens the repo can (a) bring it up and see a real result, (b) believe what the README claims, and (c) recognize AI Engineer judgment.

---

## How to read this plan

- Each task is sized for **one commit or a small PR** with a closed scope.
- **Impact**: on the portfolio impression (High / Medium / Low).
- **Effort**: `XS` < 30 min · `S` 1–2 h · `M` half a day · `L` 1–2 days.
- Within each section the tasks are **ordered by impact/effort** (best return on top).
- **Dependencies** annotated as `dep: I#`. You can start with any task that has no `dep`.
- **Verifiable** acceptance criterion: it is a command, an output, or a binary check.

Global priority scale (for orientation):
`I1 I2 I3` (minutes, extremely high return) → `I4 I5 I6` (hours, they unblock the demo) → `I7 I8` (half a day, positioning) → `W*` block (impression improvement) → `N*` block (do not touch).

---

# Must-have (blockers for showing the project)

## I1 — Return a real identifier in `POST /execute-task` and `/retry`
- **Files:** `backend/app/api/routes/orchestrator.py`, `backend/app/api/routes/retry.py`, `backend/app/schemas/orchestrator.py`, `frontend/src/services/api.ts`, `frontend/src/pages/TaskDetailPage.tsx`.
- **What/why:** today the route generates `task_id = str(uuid4())` that corresponds to nothing; the UI navigates to `/tasks/{task_id}` and shows "Task not found". Return the real `trace_id` (or `execution_id`) that does exist in the DB, and have the frontend navigate with it.
- **Acceptance:** creating a task (UI or curl) and opening the detail shows progress/report; `GET /api/v1/tasks/{returned id}` responds 200, not `Execution not found`.
- **Effort:** S · **Impact:** High · **Dep:** none.

## ~~I2 — Fix the Retry button (HTTP method + `raise`)~~ Done
- **Files:** `frontend/src/services/api.ts:93-95`, `backend/app/api/routes/retry.py:13,20`.
- **What/why:** the frontend calls `retryTask` with `GET` while the backend exposes `POST` → 405; and when the execution does not exist the handler does `return HTTPException(...)` (returns 200 with an object) instead of `raise` (404). Two three-line bugs.
- **Acceptance:** the Retry button of a failed execution creates a new execution; `POST /api/v1/task/{nonexistent trace_id}/retry` responds 404 with `{"detail": ...}`.
- **Effort:** XS · **Impact:** High · **Dep:** none.

## I3 — Remove claims the repository does not back
- **Files:** `docs/development_log.md` (week 10), `README.md` (features lines), `docs/ARCHITECTURE.md` §7 if applicable, `AGENTS.md`.
- **What/why:** the dev log says a *GitHub Actions manual-QA workflow plus issue templates* "landed" that do not exist (`.github/` only has `ci.yml`); the README promises "structured logs", "safe tool execution" and a mypy/oxlint/vitest badge that CI does not run. In a portfolio, a claim contradicted by the repo destroys credibility.
- **Acceptance:** `grep -ri "manual-QA\|issue template\|structured log" docs README.md` returns no unsupported claims; every claim in the README is verifiable with a repo command.
- **Effort:** XS · **Impact:** High · **Dep:** none.

## I4 — Make the demo work without Ollama (or make it clear it is a requirement)
- **Files:** `backend/app/core/llm/echo.py`, `backend/app/core/prompts/planner.py` (optional), `docs`/README.
- **What/why:** with the default provider (`echo`) the Planner cannot parse the response → the README's "Try it" `curl` returns `error`. Make `EchoProvider` return a **valid JSON plan** (and valid responses per agent) so the end-to-end flow produces a report without depending on Ollama; otherwise, document Ollama as a **requirement**, not "optional".
- **Acceptance:** with `LLM_PROVIDER=echo` and no Ollama, the README `curl` returns a non-null `plan` and a `report` (or, failing that, the README explicitly says `ollama pull qwen2.5:7b` is a required step).
- **Effort:** S · **Impact:** High · **Dep:** none.

## I5 — Docker: create the schema at startup and do not depend on missing scripts
- **Files:** `backend/app/main.py` (lifespan), `backend/Dockerfile`, `docker-compose.yml`.
- **What/why:** `docker compose up --build` + the README curl gives **`Internal Server Error`** because nobody runs `init_db` and the image **does not include `scripts/`**. Create the tables idempotently at startup (importing `app.models` before `create_all`) or add an `init` service in compose; and/or copy `backend/scripts` into the image.
- **Acceptance:** on a clean machine, `docker compose up --build -d && sleep 3 && curl -s -X POST localhost:8000/api/v1/execute-task -d '{"task_description":"test"}' -H 'Content-Type: application/json'` does **not** return `relation "executions" does not exist` or 500.
- **Effort:** S · **Impact:** High · **Dep:** none (test together with I4).

## I6 — Idempotency when retrying the Planner (avoid `IntegrityError`)
- **Files:** `backend/app/core/orchestrator.py:161-165`, `backend/app/core/execution_repository.py`.
- **What/why:** `run_planner` calls `create_execution(trace_id=…)` **outside** the `try`; with the `UNIQUE(trace_id)`, a second Planner failure throws `IntegrityError` → HTTP 500. Move the creation inside the error handling and use get-or-create/upsert by `trace_id` (or generate a new trace per retry and update it in the state).
- **Acceptance:** a test that re-invokes `run_planner` with an already-persisted `trace_id` does not throw `IntegrityError` and the execution ends in a controlled terminal state.
- **Effort:** S · **Impact:** Medium-High · **Dep:** none.

## I7 — Rewrite the README with the agreed section scheme
- **Files:** `README.md` (+ links to `docs/`).
- **What/why:** the current README is good but promises an "easiest path" that fails and mixes features with marketing. Rewrite it so it is **verifiable** and puts substance first. Section by section (proposed scheme):
  1. **Title + one sentence + real badges** (GitHub Actions CI; remove badges CI does not generate).
  2. **The problem** — what it solves and for whom, in 3–4 lines; why it is interesting (task → plan → research → analysis → report).
  3. **Demo** — GIF or screenshots + **a real output** (example report) so the result is visible without running anything.
  4. **Architecture** — diagram (existing mermaid) + a brief explanation of the 4 agents and the orchestrator.
  5. **Design decisions and tradeoffs** — summary table + link to the decision log in `ARCHITECTURE.md` §9.
  6. **How to run it** — Docker and local in numbered steps; **real requirements** (Docker, and Ollama + `ollama pull qwen2.5:7b` if applicable); exact `DATABASE_URL`/`REDIS_URL` values **for each mode** (host `postgres`/`redis` in Docker, `localhost` locally); a note on DB initialization.
  7. **Tests and quality** — exact commands and **what each measures**; honest coverage (mention that part of it is mocks).
  8. **Known limitations** — the already-declared ones (write-only checkpoints, cost 0.0, sandbox is not containment, no auth).
  9. **Roadmap** — the future improvements (use the `N*` block of this plan).
  10. **License.**
- **Acceptance:** following the README on a clean machine brings up the project and returns the demo result **with no undocumented steps**; every badge in the README corresponds to a real workflow.
- **Effort:** M · **Impact:** High · **Dep:** I3, I4, I5 (the README must reflect what already works).

## I8 — Add output quality evaluation (`EVALUATION.md` + smoke eval)
- **Files:** `EVALUATION.md` (new), `backend/tests/test_evaluation.py` (new).
- **What/why:** it is the biggest possible differentiator for an AI Engineer position and the most serious gap detected: today it is not measured whether the plan/report are *good*, only whether the JSON parses. Include: 3–5 example tasks with acceptance criteria, a test that validates the **structure** of the plan (3–7 steps, coherent `step_type`), and a table with a real example output and what is checked.
- **Acceptance:** `pytest tests/test_evaluation.py` passes; `EVALUATION.md` describes the dataset, the metrics, and shows at least one real output of the system.
- **Effort:** M · **Impact:** High · **Dep:** I4 (to produce a real example output).

---

# Worth it if there is time (they improve the impression)

## W1 — Ignore local artifacts and potential secrets
- **Files:** `.gitignore`.
- **What/why:** `.gitignore` does not cover `planning/`, `.claude/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/` (they are not tracked today, but a `git add .` would slip them in). Add them.
- **Acceptance:** `git status --ignored --short` lists `planning/`, `.claude/` and the caches as ignored; `git add . && git status` does not include any of them.
- **Effort:** XS · **Impact:** Medium · **Dep:** none.

## W2 — Remove obvious orphans and stubs
- **Files:** `backend/app/models/task.py`, `backend/app/models/__init__.py`, `backend/scripts/init_db.py`, `frontend/src/hooks/useApi.ts`, `backend/app/core/agents/synthesis.py` (`collect_results`), `docs/execution_db.md`, `AGENTS.md`.
- **What/why:** `Task`/`TaskStatus` is used by nobody and creates a dead `tasks` table; `useApi.ts` was replaced by TanStack Query; `collect_results` is an empty node. They remove the narrative of uncleaned iterations and are the first thing a reviewer sees.
- **Acceptance:** `grep -rn "models.task\|useApi\|collect_results" .` (excluding historical tests/docs) has no references in live code; `pytest` and `npm run build` still pass.
- **Effort:** S · **Impact:** Medium · **Dep:** none.

## W3 — Format the code and add the check to CI
- **Files:** `backend/app/core/database.py`, `backend/app/core/tracing.py`, `backend/app/schemas/base.py`, `.github/workflows/ci.yml`.
- **What/why:** `ruff format --check` fails on 3 files and CI does not run it, so the drift goes unnoticed. Format and add `ruff format --check` to the workflow.
- **Acceptance:** `ruff format --check backend/app` exits 0; CI fails if there is drift.
- **Effort:** XS · **Impact:** Medium · **Dep:** none.

## W4 — Fix the logger attribution
- **Files:** `backend/app/core/logging.py` (+ all modules that do `from app.core.logging import logger`).
- **What/why:** all modules share `logger = getLogger("app.core.logging")`, so every log reports module `logging` (visible in production: `(logging wrapper)`). Expose a `get_logger(__name__)` helper and use it per module so the trace is real.
- **Acceptance:** in the logs, `%(module)s` reflects the real emitting module (e.g. `orchestrator`, `python_executor`), not `logging`.
- **Effort:** S · **Impact:** Medium · **Dep:** none.

## W5 — Do not block the event loop in the tools
- **Files:** `backend/app/core/tools/web_search.py:28-34`, `backend/app/core/tools/python_executor.py:140-147`.
- **What/why:** `ddgs` (synchronous, network) and `subprocess.run` (up to 30 s) run inside async nodes and freeze uvicorn (SSE and `/health` included). Wrap them in `anyio.to_thread.run_sync` / `asyncio.to_thread`.
- **Acceptance:** during an execution with `python_executor`, `/health` responds < 1 s (manual test) and there are no blocking calls in coroutines.
- **Effort:** S–M · **Impact:** Medium · **Dep:** none.

## W6 — Unify dependency management (uv groups + image)
- **Files:** `pyproject.toml`, `requirements.txt`, `backend/Dockerfile`, `AGENTS.md`.
- **What/why:** `mypy`, `pytest`, `ruff`, `pre-commit` are in the runtime `dependencies` → they go into the Docker image (747 MB). Move the toolchain to a `[dependency-groups] dev` group (uv), regenerate `requirements.txt` with runtime only and split out a `requirements-dev.txt`. Update the out-of-sync pre-commit (mypy `v1.15.0` vs `>=2.3.0`; ruff `v0.11.0` vs `>=0.15.21`).
- **Acceptance:** `uv sync` installs runtime+dev; the `requirements.txt` consumed by the Dockerfile does **not** include mypy/ruff/pytest; the backend `docker images` shrinks; pre-commit uses versions consistent with `pyproject.toml`.
- **Effort:** M · **Impact:** Medium-High · **Dep:** W7 (synergy: both shrink the image).

## W7 — Harden the backend image
- **Files:** `backend/Dockerfile`, `docker-compose.yml`.
- **What/why:** it runs as root, `CMD --reload`, with no `HEALTHCHECK`. Multi-stage or at least a non-root user, remove `--reload`, add `HEALTHCHECK` and `depends_on: condition: service_healthy` for postgres/redis.
- **Acceptance:** `docker run` of the backend starts as a non-root user; `docker inspect` shows the healthcheck; compose does not start the backend before postgres is healthy.
- **Effort:** S–M · **Impact:** Medium · **Dep:** W6.

## W8 — Decide on and apply the license
- **Files:** `LICENSE`, `README.md`.
- **What/why:** GPL-3.0 (strong copyleft) is an unusual choice for a portfolio and discourages companies from reusing any fragment. To maximize dissemination, **MIT** or **Apache-2.0**.
- **Acceptance:** `LICENSE` matches the license declared in the README and in `pyproject.toml`; badge updated.
- **Effort:** XS · **Impact:** Medium · **Dep:** none.

## W9 — Drive the execution to a terminal state when the timeout expires
- **Files:** `backend/app/api/routes/orchestrator.py:36-39`, `backend/app/api/routes/retry.py:40-43`, `backend/app/core/orchestrator.py`.
- **What/why:** the 504 is raised without marking the `Execution` as `failed/timeout` or cleaning up the checkpoint → the row stays `RUNNING` forever and the SSE never closes. In the `except TimeoutError`, update status + metrics + close the stream.
- **Acceptance:** by forcing a timeout, the execution ends in `timeout`/`failed` and `GET /tasks/{id}/stream` receives a terminal event.
- **Effort:** S · **Impact:** Medium · **Dep:** none.

## W10 — Bound the re-planning loop
- **Files:** `backend/app/core/orchestrator.py:676-692,723-732,748-779`.
- **What/why:** `skip` on the last agent (`synthesis`) resets `consecutive_failures` and does not increment `total_steps`, so `check_max_steps`/`check_degradation` do not stop it (only the HTTP timeout). Count re-plan attempts or do not reset the counter on `skip` when there is no progress.
- **Acceptance:** a test with a repeated `skip` decision on the last agent ends in a bounded abort/END, not a loop.
- **Effort:** S · **Impact:** Medium · **Dep:** none.

## W11 — Unify the error scheme and clean up dead DI
- **Files:** `backend/app/schemas/base.py` (`ErrorResponse`), `backend/app/core/database.py` (`get_db`), `/execute-task` and `/retry` routes.
- **What/why:** three conventions coexist (envelope, `{"detail"}`, 200-with-error) and `ErrorResponse`/`get_db` are unused. Choose one (e.g. errors with the correct HTTP status) and use it; the `200 + error` of `/execute-task` confuses the UI.
- **Acceptance:** `ErrorResponse` and `get_db` are used or removed; the POST returns a status consistent with the result.
- **Effort:** S · **Impact:** Low-Medium · **Dep:** I1.

## W12 — Fix `data_results`, `str(None)` and history types
- **Files:** `backend/app/core/orchestrator.py:34-36,454`, `backend/app/schemas/history.py:64`, `backend/app/api/routes/history.py:99-105`, `frontend/src/types/api.ts`.
- **What/why:** `data_results` is typed `list` but is `dict`; the history converts `None` with `str()` → literal `"None"`; the TS types omit `llm_calls`/`tool_calls`. Fix the types and serialization.
- **Acceptance:** `GET /tasks/{id}` returns `null`/omitted instead of `"None"`; `mypy` adds no errors; TS types aligned.
- **Effort:** S · **Impact:** Low-Medium · **Dep:** none.

## W13 — Bring CI up to what the README promises
- **Files:** `.github/workflows/ci.yml`.
- **What/why:** CI only runs `ruff check` + pytest; it runs neither mypy, `ruff format --check`, nor frontend lint/build/tests. Add those steps (and fix `--cov=.`, which inflates coverage by including `tests/`/`scripts/`).
- **Acceptance:** the workflow runs ruff format check, mypy and (a separate job) oxlint/`tsc`/vitest; the reported coverage is only `app`.
- **Effort:** M · **Impact:** Medium · **Dep:** W3, W14.

## W14 — Harden mypy progressively
- **Files:** `pyproject.toml`.
- **What/why:** mypy passes but with loose config (`ignore_missing_imports`, no `check_untyped_defs`). Enable `check_untyped_defs` and `disallow_untyped_defs` per module/phase so typing becomes a real signal.
- **Acceptance:** `mypy app` passes with the new config; CI runs it.
- **Effort:** M · **Impact:** Low-Medium · **Dep:** none.

## W15 — Valid CORS and sanitize `X-Trace-ID`
- **Files:** `backend/app/main.py:31-37`, `backend/app/core/middleware.py:11`.
- **What/why:** `allow_origins=["*"]` with `allow_credentials=True` is invalid; the client's `X-Trace-ID` enters the logs without sanitizing (log forging). Restrict origins to configurable ones and validate the header.
- **Acceptance:** CORS uses configurable origins; an `X-Trace-ID` with control characters does not break the log format.
- **Effort:** S · **Impact:** Medium · **Dep:** none.

## W16 — Validate URLs in `web_scraper` (SSRF)
- **Files:** `backend/app/core/tools/web_scraper.py:22-33`.
- **What/why:** it does `client.get(url, follow_redirects=True)` without validating scheme/host; the README calls it "strict URL" but it is not. Block non-http(s) schemes and private/metadata ranges (`localhost`, `127.0.0.0/8`, `169.254.0.0/16`, `10/172.16/192.168`), and limit redirects.
- **Acceptance:** a test with `http://169.254.169.254/...` and `http://localhost/...` is rejected; the README stops claiming "strict URL" or it honors it.
- **Effort:** S · **Impact:** Medium · **Dep:** I3.

## W17 — Mitigate indirect prompt injection in Research/Synthesis
- **Files:** `backend/app/core/agents/research.py:117-138`, `backend/app/core/prompts/research.py`, `backend/app/core/prompts/synthesis.py`.
- **What/why:** the scraped content is injected as instructions without delimiting. Explicitly delimit untrusted content (e.g. blocks with markers), instruct the model to treat it as data and not as orders, and document it in the threat model.
- **Acceptance:** the prompts separate instructions from data and there is a test/comment documenting the defense; `ARCHITECTURE.md` includes the vector.
- **Effort:** S–M · **Impact:** Medium · **Dep:** none.

## W18 — Connection pool and `created_at` index
- **Files:** `backend/app/core/database.py:9`, `backend/app/models/execution.py`.
- **What/why:** the engine uses defaults without `pool_pre_ping`/`pool_recycle`; `list_executions` orders by `created_at` without an index. Add `pool_pre_ping=True`, `pool_recycle`, and `index=True` on `created_at`.
- **Acceptance:** the engine is created with the parameters; the listing's `EXPLAIN` uses the index.
- **Effort:** S · **Impact:** Low-Medium · **Dep:** none.

## W19 — Declare `matplotlib` or remove it from the allowlist
- **Files:** `pyproject.toml`, `backend/app/core/tools/python_executor.py:8-24`, `backend/app/core/prompts/data.py:43-45`.
- **What/why:** the sandbox allows `import matplotlib` and the prompt offers it, but it is not a dependency → all code using it fails. Add it as a dependency (or to `dependency-groups`) and fix the fact that `env={}` breaks its config, or remove it from the allowlist and the prompt.
- **Acceptance:** a snippet doing `import matplotlib` runs without `ImportError`; allowlist and prompt in sync.
- **Effort:** XS–S · **Impact:** Medium · **Dep:** W6.

## W20 — Frontend polish and stale docs
- **Files:** `frontend/index.html` (`<title>`), `frontend/README.md`, `frontend/src/components/PlanTimeLine.tsx`, `docs/orchestrator_graph.md:3`, `AGENTS.md`.
- **What/why:** the tab says "frontend"; the frontend README is the Vite template; `orchestrator_graph.md` points to a nonexistent path and is missing state fields. They are cheap signs of neglect to fix.
- **Acceptance:** `<title>Atlas Research System</title>`; a proper `frontend/README.md`; docs point to real paths.
- **Effort:** S · **Impact:** Low-Medium · **Dep:** none.

## W21 — Move the `re_plan` prompt to the registry
- **Files:** `backend/app/core/orchestrator.py:653-666`, `backend/app/core/prompts/`.
- **What/why:** it is the only inline hardcoded prompt, outside the versioned system. Move it to `core/prompts/` with `version`/`description` for consistency.
- **Acceptance:** no inline prompts remain in the orchestrator; `get_prompt("replan_*")` is used.
- **Effort:** S · **Impact:** Low-Medium · **Dep:** none.

---

# Not worth touching (it matters in production, not for a portfolio)

> These improvements would be correct in a real system, but their effort/risk is not justified for a portfolio piece. **They should be mentioned in the README's "Limitations / Roadmap" section** instead of being implemented.

- **N1 — Alembic migrations.** `create_all` is acceptable for the portfolio; Alembic adds infrastructure and startup friction without improving the impression. *Document.*
- **N2 — Background execution (Celery/ARQ) and queue.** Decoupling `graph.ainvoke` from the request is correct at scale, but it is a large redesign that is not noticed in a 15-min demo. *Document as a "scaling path".*
- **N3 — Durable checkpoints with resume (LangGraph PostgresSaver).** "Resume from checkpoint" is roadmap; implementing it is costly and is not visible in the demo. *Document.*
- **N4 — Real cost per token (`estimated_cost_usd`).** With a local model there is no cost; setting it to 0.0 and explaining it is enough. *Document.*
- **N5 — LLM token streaming.** It improves UX, does not demonstrate core competence; high cost in UI and provider. *Roadmap.*
- **N6 — Full authentication and multi-tenancy.** Out of portfolio scope; a "local demo, do not deploy without auth" notice is enough. *Document as a limitation.*
- **N7 — External observability (OpenTelemetry, Prometheus, JSON logs).** The homemade trace already demonstrates the concept; standing up the stack is overhead. *Roadmap.*
- **N8 — Dedicated read-only DB role + SQL validation with `sqlglot`/parser.** The static policy is enough for the demo; a dedicated role requires infrastructure setup. *Document as hardening.*
- **N9 — Container-isolated sandbox.** The decision log itself already acknowledges that the process sandbox is not a containment boundary; containerizing it is heavy infrastructure. *Document.*
- **N10 — Refactor of the ~220 lines of duplicated error handling in the orchestrator.** It improves maintainability, but it is a high-risk, low-visible-return refactor; the code works. *Optional long term.*
- **N11 — Full integration test suite against real Postgres / LLM contract testing.** Rewriting the entire testing strategy is weeks of work. Better: add the few integration tests from the `W` block (I6, W9, W10, W16) and **document** the mocking limitation.
- **N12 — Migration to full mypy `strict` and unifying the double ORM style.** High cost, marginal portfolio benefit; `W14` (progressive) is the sweet spot.
- **N13 — Horizontal scaling / switching SSE for WebSocket.** It does not add to the story; SSE is already a decision defended in the decision log.
- **N14 — PII redaction in stored prompts.** Relevant in production; for the portfolio it is enough to declare it.

---

## Suggested execution order (for a weekend)

| Block | Tasks | Why in this order |
|---|---|---|
| 1. Minute fixes | I1, I2, I3, W1, W3 | Maximum return per hour; the demo stops being broken and credibility is recovered. |
| 2. Unblock the demo | I4, I5, I6 | Without this, the README is not reproducible. |
| 3. Positioning | I7 (README), I8 (evals) | They depend on the demo working. |
| 4. Engineering impression | W2, W4, W5, W6, W7, W8 | Cleanup, logging, async, dependencies, Docker, license. |
| 5. Robustness / security | W9, W10, W15, W16, W17, W19 | Failures and security an engineer would ask about. |
| 6. Polish | W11–W14, W18, W20, W21 | Quality details. |

**Key dependencies:** `I7 ← I3, I4, I5` · `I8 ← I4` · `W6 ← W7` · `W13 ← W3, W14` · `W19 ← W6` · `W11 ← I1`.

---

## Closing — The 5 most likely interview questions and what to review

1. **"Walk me end-to-end through what happens in `POST /execute-task` and where it can fail."**
   Review: `backend/app/api/routes/orchestrator.py` (invoke + 600 s timeout), `backend/app/core/orchestrator.py` (nodes `run_planner/research/data/synthesis`, `check_max_steps`, `re_plan`, `check_degradation`), and `docs/ARCHITECTURE.md` §3 (sequence diagram). Know by heart the state flow and the failure points (timeout, parsing, IntegrityError).

2. **"Why 4 agents and not a single chain? What does each agent gain?"**
   Review: `docs/ARCHITECTURE.md` §9 (decision log) and §2, `backend/app/core/orchestrator.py` (`_check_if_data_needed`, routing). Prepare an honest cost/benefit answer: separation of prompts/tools/sandbox and reuse of subgraphs, acknowledging that today the pipeline is linear and that the pending value is parallelism/critique between agents.

3. **"How do you handle failures, retries and state? What happens if an agent fails or the run hangs?"**
   Review: `backend/app/core/orchestrator.py` (`re_plan`, `check_degradation`, `MAX_TOTAL_STEPS`, `save_checkpoint`/`with_checkpoint`), `backend/app/core/state_manager.py`, and the two known gaps (timeout that leaves it `running`, the `skip` loop). Be able to explain the checks and their limits.

4. **"You execute LLM-generated code and SQL. What is your threat model?"**
   Review: `backend/app/core/tools/python_executor.py` (AST allowlist, `env={}`, rlimits), `backend/app/core/tools/sql_query.py` (SELECT/WITH policy), `backend/app/core/tools/web_scraper.py` (SSRF) and decision log §9 #1/#7. Prepare the answer: it is not a containment boundary, escapes via libraries (`pandas.read_csv`), and the hardening plan (container, read-only role, URL validation).

5. **"How do you know the agents' outputs are good, not just valid?"**
   Review: `backend/tests/` (what is mocked and what is not), the `EVALUATION.md` file (which you will have written) and `backend/pytest.ini`. Be able to describe the evaluation dataset, the metrics (plan structure, groundedness/citations, coverage) and be explicit about what is **missing** (full evals, real integration).

**Extra preparation:** have at hand the commands that demonstrate each README claim (`docker compose up`, `pytest`, `ruff check`, `mypy`, `npm test`) and a real example output, because the first disguised question is always *"can I bring it up and does it work?"*.
