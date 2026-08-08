# Atlas Research System — Agent Guide

This is a learning project to build a research multi-agent system in Python. The backend is a FastAPI app with async SQLAlchemy and Redis that orchestrates LangGraph agent graphs (planner, research, data, synthesis) to execute research tasks from end to end. The frontend is a React 19 + Vite app (in `frontend/`) that creates tasks and shows live progress via SSE.

## Package management

- Python 3.13, managed with **uv** (not pip).
- Dependencies in `pyproject.toml`; `uv.lock` is the lockfile.
- Regenerate `requirements.txt` (used by Docker):
  ```
  uv pip compile pyproject.toml -o requirements.txt
  ```
- Install deps into existing venv:
  ```
  uv pip install -r requirements.txt
  ```
  Or sync from lockfile:
  ```
  uv sync
  ```

## Dev server

```sh
# from project root (env file loads from ./backend/../.env)
uvicorn app.main:app --reload --port 8000
```
Run from `backend/` so the `.env` relative path resolves correctly (config expects `.env` at project root).

Or use Docker Compose:
```sh
docker compose up --build
```

## Environment

Copy `.env.example` to `.env` at project root. Required vars:
- `DATABASE_URL` — asyncpg DSN (`postgresql+asyncpg://user:pass@host:port/db`)
- `REDIS_URL` — e.g. `redis://localhost:6379`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`

## Architecture notes

- **Entrypoint**: `backend/app/main.py` — FastAPI app with CORS, version `0.1.0`.
- **Config**: `backend/app/config.py` — Pydantic `BaseSettings`, reads `.env` via `lru_cache`.
- **Database**: `backend/app/core/database.py` — async SQLAlchemy engine, `declarative_base`, `async_sessionmaker`.
- **Models**: `backend/app/models/` — SQLAlchemy ORM models (`execution.py`: `Execution`, `ExecutionStep`, `ExecutionMetricsCache`, `LLMCall`, `ToolCallRecord`; `task.py`: `Task`).
- **Schemas**: `backend/app/schemas/` — Pydantic request/response models (one per domain: plan, research, data, orchestrator, history, stats, llm).
- **API routes**: `backend/app/api/routes/` — FastAPI `APIRouter` modules (health, llm, plan, research, data, orchestrator, history, stream, stats, retry), all under `/api/v1`.
- **Core services**: `backend/app/core/` — database, logging (colorlog-based structured logs), redis_client, state_manager, execution_repository, orchestrator (LangGraph), agents, tools, llm providers, tracing, middleware.
- **Frontend**: `frontend/` — React 19 + Vite + TanStack Query + react-router; SSE via `EventSource` for live execution progress (architecture doc in `docs/ARCHITECTURE.md`).
- **Tooling**: pytest + pytest-asyncio (backend tests in `backend/tests/`), ruff + mypy + pre-commit; frontend uses oxlint + vitest.

## Docker

- **Dockerfile**: `backend/Dockerfile` (python:3.13-slim, copies `requirements.txt` then `./backend/app`).
- **docker-compose.yml** at root: backend + postgres:15-alpine + redis:7-alpine + frontend (nginx on :8080).

## Initializing the database

```sh
python backend/scripts/init_db.py
```
Creates all tables via SQLAlchemy metadata.

## Known quirks

- `.env` is loaded by `pydantic-settings` from `Path(__file__).parent.parent.parent / ".env"` i.e. project root. If running uvicorn from a different directory, the env file won't be found.
- `/health` probes Redis (`ping`) and Postgres (`SELECT 1`) with a 2s socket timeout.
- Checkpoints are written to Redis (`orchestrator:{id}`) but resume-from-checkpoint is not implemented.
