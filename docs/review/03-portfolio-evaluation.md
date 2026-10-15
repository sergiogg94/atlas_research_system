# Portfolio evaluation — Hiring Manager view (AI Engineer)

**Repository:** `sergiogg94/atlas_research_system` · **Evaluator:** technical hiring manager (AI company) · **Date:** 2026-10-15
**Method:** 15 minutes of initial attention, as in a real portfolio review. I cloned the repo, followed the README **literally**, brought up the app and tested the documented flow. I read `README.md`, `docs/ARCHITECTURE.md`, `docs/development_log.md`, reviews `01`/`02`, CI, tests, git history and license.

> **How to read this document.** It is not a code review (that is already in `01-diagnostico.md` and `02-auditoria.md`). It is what a technical recruiter concludes on the first pass, and what they would decide about a CV with this repo as the main piece. It is harsh on purpose: the goal is for the project to be ready for a portfolio.

---

## 0. 30-second verdict

**Yes, I would take it to a technical interview — but with reservations and with uncomfortable questions.**

The repo shows the author **knows how to build** (LangGraph, async SQLAlchemy, SSE, custom tracing, Docker, CI, 186 commits in ~2 months, unusually good architecture documentation). That is not trivial and passes the first filter of "does this person actually implement?".

What it **does not yet** show is **production judgment or evaluation rigor**: the flow the README promises **does not work out-of-the-box** (I verified it), the high coverage is a mirage of mocks, the multi-agent architecture is not justified with data, there is no quality evaluation of the LLM outputs, and there are statements in the documentation that the repo itself contradicts.

**Profile read:** a junior-to-mid engineer strong in *software engineering*, nascent in *AI engineering* (prompting, evaluation, LLM robustness, tool-use security). Learning in public with discipline is a real plus; overselling maturity that is not there is the risk.

If I had 1 hour to improve it before a recruiter opens it: **(1)** make `docker compose up` work and the README curl return a report, **(2)** delete unsupported claims, **(3)** write an honest `EVALUATION.md` with a real example output. That changes perception more than any refactor.

---

## 1. First impression and reproducibility (I followed the README literally)

### What I did, exactly as the README says

```sh
git clone …/atlas_research_system           # clean repo (143 tracked files)
cp .env.example .env                        # §1
# I filled in POSTGRES_USER/PASSWORD/DATABASE_URL/REDIS_URL (§1)
docker compose up --build                   # §2a — "easiest path"
curl -X POST …/api/v1/execute-task -d '{"task_description": "Explain how transformers work …"}'   # §3
```

### What happened, step by step

| README step | Real result |
|---|---|
| `docker compose up --build` | Starts… but **fails due to a container-name conflict** if you have run the project before (`container_name:` hardcoded in compose). |
| `GET /api/v1/health` | ✅ `{"status":"healthy", "services":{"redis":"healthy","database":"healthy"}}` |
| `POST /api/v1/execute-task` (the README curl) | ❌ **`Internal Server Error`** |
| Cause in logs | `asyncpg.exceptions.UndefinedTableError: relation "executions" does not exist` |
| `init_db.py` | README §2b mentions it **only** for the local flow; **§2a (Docker) never runs it** and `docker-compose.yml` does not run it either. Worse: the `Dockerfile` only copies `./backend/app`, so **`scripts/init_db.py` is not even inside the image** — there is no way to initialize the DB in Docker. |
| After creating tables by hand | `POST /execute-task` returns **HTTP 200** with `{"status":"success", "error":"Planner failed: Failed to parse plan: Expecting value…", "report":null, "task_id":"9121b852…"}` |
| Why it fails with the default provider | With `llm_provider=echo` (or without Ollama) the Planner cannot parse the response → no report. The README says Ollama is *"optional but recommended"*, but **in practice Ollama + `qwen2.5:7b` is mandatory** for the demo to produce anything. |
| Bug visible instantly | The returned `task_id` (`9121b852…`) **is not the real `trace_id`** (`925be9ca…`). The frontend navigates to `/tasks/9121b852…` → `{"detail":"Execution not found"}`. **Creating a task in the UI and viewing the detail is the central flow of the README and it is broken.** |
| Frontend | ✅ serves on :8080 (nginx), but the tab says `<title>frontend</title>` (untouched Vite template). |

### Why this matters enough to condition the verdict

A recruiter spends **minutes**, not hours. The "click and it works" path is the first thing tested, and the README promises it explicitly ("easiest path", "Try it"). The flagship command returning `Internal Server Error` **before** seeing a single line of code already biases the whole reading: the evaluator shifts from "let's see what they can do" to "let's see if it works, and if not, why not". The rest of the repo then competes against that first impression, instead of adding to it.

### The README as a document (a real strength, with caveats)

- **Good**: it explains the problem, the architecture (mermaid), the 4 agents, the technical-decisions table with links to the decision log, the roadmap of limitations, and even the note about the `.env` quirk. It is **far above** the average portfolio README. The declared honesty ("write-only checkpoints", "cost 0.0", "sandbox is not containment") is a strong positive signal.
- **Bad (ambiguities that cost time)**:
  - It is not clear which values to use in `DATABASE_URL` for each mode. In Docker the host must be `postgres` and Redis `redis`; locally, `localhost`. `.env.example` ships `REDIS_URL=redis://redis:6379` and `DATABASE_URL=…@HOST:PORT/…`, so **the example does not work as-is for either flow** without deducing what to replace.
  - It does not say that tables must be created in the Docker flow, nor that you need `ollama pull qwen2.5:7b` for the curl to make sense.
  - The "run from backend/" instructions and the `.env` quirk are in a note, easy to skip.

---

## 2. Is the multi-agent design justified?

**Honest answer: partially, and it is not demonstrated — but it is defensible as a learning project.**

In favor of yes:
- There are **4 roles with distinct responsibilities**, not 4 labels: the Data agent has its own Python/SQL sandbox and a **self-reflection loop** (`reflect_error` → regenerate code ≤3), the Research agent orchestrates web tools, the Planner produces a validated Pydantic `Plan`, Synthesis validates and retries. Each agent has its versioned prompts and its validation.
- There is **real conditional routing** (Data only enters if the plan "needs data") and a `re_plan` node that **asks the LLM to decide** `retry|skip|abort` — the latter is the most genuinely "agentic" part of the system: control flow decided by the model.
- The LangGraph subgraphs are a coherent technical decision (composing reusable graphs, not a monolithic `if/else`).

Against it being justified (what I would ask):
- The pipeline is, in essence, **a linear chain** (`planner → research → (data) → synthesis`) with one optional branch. There is no **parallelism** between agents, no **negotiation or debate**, no **dynamic decomposition** beyond the initial plan. A sequential `run(task)` function with conditional steps would do the same with less surface area.
- The decision "is the Data agent needed?" **is not made by an agent**: it is a **keyword heuristic** over the plan steps (`_check_if_data_needed`), with a bug (a short-circuited `or` that means `step_type` is never consulted). That is, the piece that *should* justify the multi-agent orchestration is solved in the least "agentic" way possible.
- There is no evidence, neither in the README nor in the docs, of **why separating into agents improves results** versus a single long call or a chain. There is no A/B, no quality metric, no case where the multi-agent assembly wins. The justification is implicit ("it is a multi-agent system") and about scaffolding, not empirical.

**How I score it:** as a *demonstration that you know how to orchestrate agents with LangGraph*, it delivers and is one of the strongest parts of the repo. As an *argument that the problem requires several agents*, it is not done. In an interview, this is exactly the kind of "why not a single prompt?" that separates whoever copied the pattern from whoever understands the cost/benefit.

---

## 3. Real understanding of the concepts

**There is real understanding, with concrete gaps in the "AI-native" parts.**

Evidence of understanding (strong signals):
- **Orchestration and state**: it handles typed state (`TypedDict`), checkpoints, limits (`MAX_TOTAL_STEPS`, `DEGRADATION_THRESHOLD`), and conditional routing. The `development_log` explains *why* a StateGraph and not a linear chain. That is design judgment, not copying.
- **Recovery**: there is a serious effort to recover from failures (LLM re-planning, the Data agent's self-reflection, backoff with tenacity). The fact that it acknowledges in the decision log that "HTTP 5xx is not retried" and that "checkpoints are write-only" indicates self-awareness of the limits.
- **Tracing**: ContextVars, cross-cutting `trace_id`, persistence of `llm_calls`/`tool_calls`. It understands that in systems with LLMs you must be able to reconstruct what happened.
- **Decision documentation**: the **decision log in `ARCHITECTURE.md` §9** (11 decisions with "chosen / why / trade-offs / future alternative") is **the best thing in the repo and the hardest to fake**. The weekly `development_log.md` with "Key Learnings" and "Pending items" is also a genuine engineering diary.

Gaps an interviewer would spot quickly:
- **No quality evaluation**: there is not a single metric for "is the plan good?", "is the report grounded?", "do the findings cite well?". The system is only tested against "it does not throw" and "the JSON parses". For an AI Engineer position, **this is the most serious gap**: it knows how to *orchestrate* LLMs, but not how to *measure* whether they work.
- **Fragile and inconsistent LLM parsing**: the Planner does a bare `json.loads`; the Data agent does strip markdown fences. Different strategies coexist with no common helper, and structured output is not exploited (Ollama's `format=json`, langchain-core's `PydanticOutputParser`, which is already a dependency). A sign that it "was made to work" instead of designing for robustness.
- **Awareness of LLM limits**: partial. It partially acknowledges runaway loops (the two hard limits do not cover the re-planning loop, see review 02 §1.1), but there is no real cost/token control, no streaming, and no context limits beyond truncating to 1000/3000 chars.
- **Tool-use security**: the sandbox and the "read-only" SQL are presented as safe, but they are heuristics (the decision log itself admits it). It also shows no awareness of **indirect prompt injection** from scraped content — the most relevant vector in a system that reads the web and executes LLM-generated code. It does not appear in the threat model.

**Verdict:** it can explain and defend its decisions (good), but its understanding of *evaluation*, *structured output* and *agent security* is still beginner-level. That is where an interviewer would dig deeper.

---

## 4. Engineering maturity

**It is a system, not a script — but a "development" system, not a production one.**

| Dimension | Real state | Verdict |
|---|---|---|
| **Structure** | Clear layers: routes / schemas / core / agents / tools / llm / models. Coherent. | ✅ Good |
| **Typing** | `mypy` passes (59 files), but loose config (`ignore_missing_imports`, no strict). It is **type-checked, not type-safe**. | ⚠️ Acceptable |
| **Lint/format** | Clean `ruff check`, **but `ruff format --check` fails on 3 files** and CI does not run it. | ⚠️ |
| **Tests** | 229 tests pass in 4s; app coverage ~89%. But **233 uses of mocks**; the most complex method (the `ON CONFLICT` upsert) is **0% covered**, `conftest.reset_db` resets nothing, and the bug that breaks production (`UNIQUE(trace_id)` on retry) has no test. **High coverage, low confidence.** | ❌ Mirage |
| **CI** | `ci.yml` with Postgres/Redis services, `uv sync`, `init_db`, pytest+Codecov. **But it runs neither mypy, nor `ruff format`, nor the frontend tests/build.** The README's "quality" badge mentions mypy/oxlint/vitest that CI does not run. | ⚠️ Incomplete |
| **Config** | Centralized `pydantic-settings` and complete `.env.example`. But **insecure defaults** (`DEBUG=True`, `LOG_LEVEL=DEBUG`) and behavior constants scattered through the code. | ⚠️ |
| **Logging** | colorlog + ContextVars + `trace_id`. **But the logger is misattributed in all 22 modules** (everything comes out as module `logging`; visible in the logs I captured: `(logging wrapper)`), and there are no JSON logs. The README's "structured logging" is text with colors. | ⚠️ |
| **Deployment** | Multi-service Docker Compose + containerized frontend (multi-stage, nginx SSE-safe). **But**: the backend image is **747 MB** single-stage with dev-deps, runs as **root**, `CMD --reload`, **no HEALTHCHECK**, compose without healthchecks, code bind-mount. It is a **development** stack presented as the way to deploy. | ⚠️ Dev-grade |
| **Migrations** | **No Alembic**; `create_all`. Changing the schema = by hand. | ❌ Missing |
| **Dependencies** | `uv` + `uv.lock` + synced `requirements.txt` (good). **But dev-deps in the main `dependencies`** → they go into the image. | ⚠️ |

**Conclusion:** the "process" engineering (structure, tooling, CI, containers, docs) is above the portfolio average. The "production" engineering (migrations, healthchecks, secure config, non-root user, dev/prod separation, real observability) barely exists, and several README statements (structured logs, mypy in quality, safe sandbox) read as aspirational rather than factual.

---

## 5. Git history and process

**A strong, positive signal.** 186 commits, ~2 months, near-daily cadence, **Conventional Commits** (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`), atomic commits with messages that explain the what. A real iterative process is visible: backend first, then agents, tools, frontend, tests, containerization. For a portfolio repo, this is among the most convincing things: **it shows persistence and sustained work**, not a final dump.

Caveats an evaluator will notice:
- **Typos in messages and code** (`Bassic backend structure`, `bassic logger`, `update reame`, `arquitecture`) and **mixed Spanish/English** in comments, messages, and the `planning/` folder (which luckily **is not tracked**, `git ls-files` does not include it). It betrays haste and lack of review.
- No branches/PRs: everything to `main`. Normal for a solo project, but **it does not demonstrate teamwork** (even though the dev log talks about "workflow" and "issue templates" that do not exist).
- A single author. No collaboration to evaluate.

---

## 6. Red flags

Ordered by impact on a hiring decision:

1. **❌ The README's "happy path" does not work** (Internal Server Error → then echo parse error → navigation broken by a phantom `task_id`). It is the most damaging signal because it is the first. It breaks the trust relationship before the code is even evaluated.
2. **❌ Claims not backed by the repo**:
   - `development_log.md` (week 10) says a *GitHub Actions manual-QA workflow plus issue templates* "landed" → in `.github/` **only `ci.yml` exists**. In a portfolio, a claim the repo contradicts is a credibility red flag (what else is aspirational?).
   - README "structured logs" → text logs; "safe tool execution" → heuristics; mypy/oxlint/vitest badge → CI does not run them.
3. **❌ No evaluation of the LLM outputs.** For an AI Engineer role this is a foundational gap, not polish. There is no way to tell whether the system produces *good* answers.
4. **⚠️ Overengineering relative to the problem**: 4 agents, subgraphs, checkpoints, LLM re-plan… for a pipeline that is linear and whose branching is a keyword heuristic. It is not serious (it is a learning project and the architecture is defensible), but a senior evaluator will read it as "I liked the multi-agent pattern and applied it".
5. **⚠️ Orphan files and features**: `models/task.py` (`Task`) unused, `useApi.ts` replaced by TanStack Query, stubs (`collect_results`), dead state fields, duplicated `MetricCard`, untouched `frontend/README.md`. They tell the story of past iterations left uncleaned.
6. **⚠️ 747 MB Docker image** with the development toolchain, root, and `--reload`. A sign that "Docker" was solved to make it work locally, not to deploy.
7. **⚠️ GPL-3.0 license**: an unusual choice for a portfolio. As learning code it is fine, but **strong copyleft is exactly what many companies do not want to touch** (they cannot reuse even fragments in proprietary products without contaminating them). For a portfolio, **MIT or Apache-2.0 maximize dissemination and prevent a tech lead from discarding it as a reference or a base**. It is not a "no", but it is a decision an evaluator registers.
8. **⚠️ No auth, an endpoint that executes code, CORS `*` with credentials**: expected in an MVP, but the README should frame it more strongly as "local demo, do not deploy like this".

**What is NOT a red flag** (and it is important to say it): there are no secrets in the repo (`.env` is ignored and untracked), no leaked `planning/` or `.claude/`, and the decision log is honest. The author **knows** their limits; the problem is that the README sometimes sounds more mature than it is.

---

## 7. The 10 hardest technical questions I would ask

With what I would expect to hear in a **good** answer (not the perfect answer, but the one that shows judgment).

**1. Explain the execution model and what exactly happens when the `asyncio.wait_for(600)` of `/execute-task` expires.**
*Good answer:* acknowledges that the timeout raises 504 **without** driving the `Execution` to a terminal state or cleaning up the Redis checkpoint; that the row stays `RUNNING` forever and the SSE never closes; and proposes an `except TimeoutError` that marks `failed/timeout` + `compute_and_upsert_metrics` + closes the stream. If they do not see it, it means they have never debugged a hung run.

**2. Your `re_plan` with `skip` on Synthesis resets `consecutive_failures` to 0 and the synthesis failure does not increment `total_steps`. Can it loop forever? How do you demonstrate it?**
*Good answer:* yes, on the last agent `skip` returns to `synthesis` without `check_max_steps` or `check_degradation` stopping it; today only the HTTP timeout cuts it. Good: separate "the LLM said skip" from "no progress" (a max number of re-plans, or have `total_steps` count re-plan attempts).

**3. Justify the multi-agent architecture. What would break if you collapsed it into a single sequential function?**
*Good answer:* honest and concrete — separation of prompts/tools/sandbox per role, reuse of subgraphs, and above all that the real value would be in parallelizing research or in having agents that critique each other; admits that today the "needs data" decision is a heuristic and that there is **no empirical evidence** that 4 agents beat 1. Bad: defending the pattern because "it is multi-agent" with no cost/benefit.

**4. Your sandbox is based on an AST allowlist + `env={}` + rlimits. But `pandas.read_csv('/etc/passwd')` or `pd.read_csv('http://169.254.169.254/…')` do not go through the `open()` you block. What is your threat model and what is the real fix?**
*Good answer:* acknowledges that the AST allowlist only blocks the obvious surface and that **the allowed libraries evade the control**; that it is not a containment boundary; proposes real process isolation (container/seccomp/unprivileged user, no network) and a read-only DB role. This shows whether they understand agent security versus input validation.

**5. The Planner does a bare `json.loads`, the Data agent strips markdown fences. Why the inconsistency and how would you make structured output reliable at scale?**
*Good answer:* a common extraction/parsing helper, Pydantic schemas as a contract, the provider's `response_format`/`format=json`, retry with "your JSON did not validate, fix it", and semantic validation (not just syntactic). Mentioning that LLMs drift even when you use `format=json`.

**6. How do you evaluate that the agents produce *good* outputs, not just valid JSON? What is in your eval harness?**
*Good answer:* a dataset of tasks with expected outputs/worst cases, automatic judges + human review on a subset, groundedness/citation metrics, plan coverage, hallucination rate, regression per versioned prompt. If they answer "I did not do it, but I would do it this way…", it adds; if they do not see the problem, it subtracts a lot for an AI Engineer position.

**7. 89% coverage and `compute_and_upsert_metrics` at 0%; the `UNIQUE(trace_id)` bug only shows up in production. What is wrong with your testing strategy?**
*Good answer:* coverage ≠ confidence; mocks turn tests into tautologies; it lacks real integration against Postgres (including constraints), LLM contract tests with Ollama doubles, and tests of the failure paths (5xx, timeout, cancellation). Acknowledges the empty `reset_db`.

**8. `create_execution` is outside the `try` in `run_planner` and `trace_id` is UNIQUE. Walk me through the retry path and the `IntegrityError`. How would you make the pipeline idempotent?**
*Good answer:* identifies that retrying the Planner re-inserts the same `trace_id` and blows up outside the error handling → 500; proposes upsert/get-or-create by `trace_id`, moving the creation inside the error handling, and an idempotency key on the creation POST.

**9. In production a run fails. All logs say module `logging`, `LLMCall.model` is always NULL, and the trace writes are `ensure_future` without a reference. How do you debug?**
*Good answer:* admits that the trace lies (misattributed logger, model not recorded) and that fire-and-forget writes are lost on cancellation; proposes `getLogger(__name__)` per module, correlated JSON logs, recording the real model, and retaining/awaiting the tracing tasks. This question measures whether they blindly trust their observability.

**10. You have full prompts in Postgres, an unauthenticated endpoint that executes code, and CORS `*` with credentials. Prioritize what you fix first for a real deployment and why.**
*Good answer:* prioritizes by risk surface (auth + rate-limit on the execution endpoint, then a least-privilege DB role and sandbox network, then valid CORS, then redaction of prompts/PII); understands that the endpoint executing LLM-generated code is the most exposed. Bad: "I would add auth someday".

---

## 8. What I would fix before publishing (by hiring impact)

1. **Make the README work literally**: `init_db` at startup (or an init service in compose), include `scripts/` in the image, state the `DATABASE_URL`/`REDIS_URL` values per mode explicitly, and clarify that Ollama is a **requirement** for the demo (or ship a fixture with `echo` that returns a valid plan).
2. **Fix the phantom `task_id`** (have the POST return the real `trace_id`/`execution_id`). Without this, the central UI flow is broken and the first thing an evaluator does when clicking fails.
3. **Delete/replace unsupported claims**: the nonexistent QA workflow in the dev log, "structured logs", "safe sandbox", the mypy/oxlint/vitest badge. Honesty is already a strength of the repo; do not let marketing ruin it.
4. **Add evaluation**: an `EVALUATION.md` with 3–5 tasks, an example of real output and what is measured. It is the biggest possible differentiator for an AI Engineer.
5. **Raise CI to match the README**: mypy + `ruff format --check` + frontend build/tests; and separate dev-deps (uv dev group).
6. **Cleanup**: delete `Task`/`task.py`, `useApi.ts`, stubs and dead fields; the frontend `README`; the app `<title>`.
7. **Harden Docker**: multi-stage, non-root user, no `--reload`, healthchecks, no dev-deps → a much smaller image.
8. **Decide on the license**: if the goal is a portfolio, **MIT/Apache-2.0** communicates "use it however you want"; GPL-3.0 communicates something else and scares reuse away.

---

## 9. Final recommendation

**Move to a technical interview.** There is demonstrable substance (orchestration, async, tracing, Docker, CI, engineering diary, 186 commits) and uncommon honesty in the decision documentation. It is exactly the profile you want to interview to see how far the judgment goes.

**But the repo, as it stands, does not pass the "I open it and it works" test.** That is not an aesthetic detail: in portfolios, the first impression is binary. A weekend of work (points 1–3 and 5 of the previous section) turns this repo from "good with asterisks" into "clearly hirable". The gap between who the author is and what the repo communicates is today the biggest gap — and, luckily, the cheapest to close.
