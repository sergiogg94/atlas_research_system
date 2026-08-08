# API Reference

Complete reference of the HTTP endpoints exposed by the Atlas Research System backend.

- **Base URL**: `http://localhost:8000`
- **Prefix**: all routes are under `/api/v1`
- **Interactive documentation (Swagger UI)**: http://localhost:8000/docs — also available as ReDoc at http://localhost:8000/redoc
- **OpenAPI spec**: generated automatically by FastAPI from the Pydantic schemas.

## Endpoint summary

| Method | Path | Router | Description |
|---|---|---|---|
| `GET` | `/health` | health | Liveness probes for Redis and PostgreSQL |
| `POST` | `/test/generate` | llm | Smoke-test the configured LLM provider |
| `GET` | `/test/models` | llm | List models available from the provider |
| `POST` | `/plan` | plan | Run the Planner agent standalone |
| `POST` | `/research` | research | Run the Research agent standalone |
| `POST` | `/data` | data | Run the Data agent standalone |
| `POST` | `/execute-task` | orchestrator | Full pipeline: Planner → Research → (Data) → Synthesis |
| `POST` | `/task/{trace_id}/retry` | retry | Re-execute a task's description |
| `GET` | `/tasks` | history | List executions (paginated) |
| `GET` | `/tasks/{trace_id}` | history | Execution detail (steps, LLM & tool calls, report) |
| `GET` | `/tasks/{trace_id}/metrics` | history | Per-execution metrics cache |
| `GET` | `/tasks/{trace_id}/stream` | stream | SSE — live progress events |
| `GET` | `/stats` | stats | Aggregated execution statistics |

## Conventions

- **Success responses** embed `status` and `timestamp` (all models inherit `BaseResponse`).
- **Errors** — FastAPI `HTTPException` bodies: `{"detail": "..."}` with:
  - `400` — invalid input / agent error (e.g. planner parse failure)
  - `404` — execution or metrics not found
  - `504` — timeout (LLM generation, planner, research, data, full task)
- **Task statuses**: `pending`, `running`, `completed`, `failed`, `timeout`.
- **Trace ID**: optional `X-Trace-ID` request header; if present it is echoed in the response header and used to correlate logs/DB records (a fresh one is generated otherwise).

---

## GET /api/v1/health

Health check that probes Redis (`PING`, 2s socket timeout) and PostgreSQL (`SELECT 1`).

**Response 200**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": { "redis": "healthy", "database": "healthy" },
  "timestamp": "2026-08-08T10:00:00-06:00"
}
```

`status` becomes `degraded` and the failing service `unhealthy` when a probe fails.

---

## POST /api/v1/test/generate

Test generation with the configured LLM provider (`echo` or `ollama`).

**Body**

| Field | Type | Constraints |
|---|---|---|
| `prompt` | string | required · 1–4000 chars |
| `system` | string \| null | optional · ≤ 2000 chars |

**Response 200**

```json
{
  "status": "success",
  "provider": "OllamaProvider",
  "response": "…model answer…",
  "timestamp": "…"
}
```

**504** — provider timed out.

## GET /api/v1/test/models

**Response 200**

```json
{ "status": "success", "provider": "OllamaProvider", "models": ["qwen2.5:7b"], "timestamp": "…" }
```

---

## POST /api/v1/plan

Runs the Planner subgraph (validate → LLM → parse) and returns the structured plan.

**Body**

| Field | Type | Constraints |
|---|---|---|
| `task_description` | string | required · 10–2000 chars |

**Response 200**

```json
{
  "status": "success",
  "plan": {
    "objective": "Explain how transformers work",
    "assumptions": ["Audience has basic ML background"],
    "steps": [
      {
        "step": 1,
        "action": "Research the transformer architecture",
        "expected_output": "Summary of attention and self-attention",
        "step_type": "research"
      }
    ]
  },
  "timestamp": "…"
}
```

`step_type` ∈ `scoping|research|analysis|synthesis`. **400** when generation or parsing fails. **504** on timeout.

---

## POST /api/v1/research

Runs the Research subgraph over the given steps (each step: web search → scrape top 3 URLs → LLM summary).

**Body**

| Field | Type | Constraints |
|---|---|---|
| `objective` | string | required · 10–1000 chars |
| `steps` | array of objects | required · ≥ 1 item (plan steps, each with e.g. `action`) |

**Response 200**

```json
{
  "status": "success",
  "objective": "…",
  "findings": [
    { "step": 1, "query": "transformer architecture explained", "summary": "…" }
  ],
  "total_steps": 3,
  "timestamp": "…"
}
```

**400** if any step fails. **504** after 600 s timeout.

---

## POST /api/v1/data

Runs the Data subgraph (analyze → generate code → classify → execute python/sql → reflect on error, ≤ 3 retries).

**Body**

| Field | Type | Constraints |
|---|---|---|
| `task` | string | required · 10–2000 chars |
| `context` | string | optional · ≤ 5000 chars (default `""`) |
| `max_iterations` | integer | optional · 1–5 (default 3) |

**Response 200**

```json
{
  "status": "success",
  "task": "…",
  "code": "import pandas …",
  "query": null,
  "result": { "stdout": "…", "stderr": "", "returncode": 0, "plots": [] },
  "error": null,
  "iterations": 1,
  "timestamp": "…"
}
```

**504** after 180 s timeout.

---

## POST /api/v1/execute-task

Executes the full pipeline end-to-end through the orchestrator graph. Blocks until the run finishes (600 s timeout).

**Body**

| Field | Type | Constraints |
|---|---|---|
| `task_description` | string | required · 10–2000 chars |

**Response 200**

```json
{
  "status": "success",
  "task_id": "8f2e4b9a-…",
  "objective": "Explain how transformers work",
  "plan": { "objective": "…", "assumptions": [], "steps": [] },
  "research_findings": [ { "step": 1, "query": "…", "summary": "…" } ],
  "data_results": { "stdout": "…", "returncode": 0, "plots": [] },
  "report": "…final markdown report…",
  "error": null,
  "total_steps": 4,
  "timestamp": "…"
}
```

Lifecycle is persisted as an `execution` row keyed by a `trace_id` that is independent from the response's `task_id` (a client-side correlation id). To watch progress via SSE, send your own `X-Trace-ID` header on the execute call or look up the run afterwards with `GET /api/v1/tasks`. **504** if the full run exceeds 600 s.

## POST /api/v1/task/{trace_id}/retry

Starts a new execution using the `task_description` of a previous execution.

**Path params**

| Param | Description |
|---|---|
| `trace_id` | trace id of the execution to retry |

**Response**: same shape as `/execute-task`. **404** if no execution matches the trace id.

---

## GET /api/v1/tasks

Paginated list of executions.

**Query params**

| Param | Type | Constraints | Default |
|---|---|---|---|
| `page` | integer | ≥ 1 | 1 |
| `page_size` | integer | 1–100 | 20 |
| `status` | string | `pending|running|completed|failed|timeout` | all |
| `q` | string | ≤ 200 chars, substring match on `task_description` | — |

**Response 200**

```json
{
  "status": "success",
  "executions": [
    {
      "id": "…uuid…",
      "trace_id": "…uuid…",
      "task_description": "Explain how transformers work…",
      "objective": "…",
      "status": "completed",
      "total_steps": 4,
      "error": null,
      "started_at": "…",
      "completed_at": "…",
      "created_at": "…",
      "updated_at": "…"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "timestamp": "…"
}
```

## GET /api/v1/tasks/{trace_id}

Full execution detail: plan, report, steps, LLM calls and tool calls.

**Path params**: `trace_id` — execution trace id (UUID).

**Response 200** — `execution` extends the summary with:

- `plan: dict | null`
- `report: string | null`
- `steps: []` — `id`, `execution_id`, `trace_id`, `agent_name`, `step_type`, `input_summary`, `output_summary`, `status`, `error`, `latency_ms`, `created_at`
- `llm_calls: []` — `prompt_preview`, `system_prompt`, `user_prompt`, `response`, `model`, `latency_ms`, `estimated_tokens_input`, `estimated_tokens_output`, …
- `tool_calls: []` — `tool_name`, `input`, `output_preview`, `status`, `error`, `latency_ms`

**404** if the execution does not exist.

## GET /api/v1/tasks/{trace_id}/metrics

Materialized metrics for an execution (computed at terminal states).

**Response 200**

```json
{
  "status": "success",
  "metrics": {
    "execution_id": "…uuid…",
    "trace_id": "…uuid…",
    "total_duration_ms": 83241,
    "total_llm_calls": 7,
    "total_tool_calls": 5,
    "total_steps": 4,
    "total_tokens_input": 6402,
    "total_tokens_output": 1840,
    "estimated_cost_usd": 0.0,
    "avg_step_latency_ms": 3200.5,
    "avg_llm_latency_ms": 2101.0,
    "error_count": 0
  },
  "timestamp": "…"
}
```

**404** if metrics were never computed.

---

## GET /api/v1/tasks/{trace_id}/stream

SSE endpoint for live execution progress. The server polls the DB every 1 s and pushes an event only when something changed.

**Path params**: `trace_id` (UUID).

**Events** (`text/event-stream`):

| Event | Payload (`data`) | Emitted |
|---|---|---|
| `progress` | `{ trace_id, status, total_steps, plan, steps[] }` | when status/step count changed |
| `complete` | previous payload + `metrics` + `report` | terminal state (`completed`/`failed`/`timeout`) — then the stream closes |
| `error` | `{ message }` | execution not found or server error |

Example client usage (browser):

```js
const es = new EventSource("/api/v1/tasks/{trace_id}/stream");
es.addEventListener("progress", (e) => console.log(JSON.parse(e.data)));
es.addEventListener("complete", (e) => console.log(JSON.parse(e.data)));
```

> The UI keeps the stream open for the whole run; on `complete` it closes the connection (`EventSource.close()`).

---

## GET /api/v1/stats

Aggregated statistics across all executions.

**Response 200**

```json
{
  "status": "success",
  "stats": {
    "total": 42,
    "completed": 31,
    "failed": 8,
    "timeout": 3,
    "avg_duration_ms": 65210,
    "success_rate": 73.8,
    "recent_executions": [
      { "trace_id": "…", "task_description": "…", "status": "completed", "created_at": "…" }
    ]
  },
  "timestamp": "…"
}
```

> `success_rate` is recomputed on each call (`completed / total × 100`); `recent_executions` holds the last 5.
