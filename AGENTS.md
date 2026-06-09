# Atlas Research System — Agent Guide

This is a learning project to build a research multi-agent system in Python. The backend is a FastAPI app with async SQLAlchemy and Redis, designed to manage agents, tasks, and results. The frontend is planned as a React app but not implemented yet.

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
- **Models**: `backend/app/models/` — SQLAlchemy ORM models (e.g. `Task` with UUID PK, status enum).
- **Schemas**: `backend/app/schemas/` — Pydantic request/response models.
- **API routes**: `backend/app/api/routes/` — FastAPI `APIRouter` modules (currently only `health`).
- **Core services**: `backend/app/core/` — database, logging (colorlog-based structured logs).
- **No frontend yet** — planned React app (architecture doc in `docs/arqutecture.md`).
- **No tests, no linter, no type checker configured** — these must be added before running anything in that category.

## Docker

- **Dockerfile**: `backend/Dockerfile` (python:3.13-slim, copies `requirements.txt` then `./backend/app`).
- **docker-compose.yml** at root: backend + postgres:15-alpine + redis:7-alpine.

## Initializing the database

```sh
python backend/scripts/init_db.py
```
Creates all tables via SQLAlchemy metadata.

## Known quirks

- `.env` is loaded by `pydantic-settings` from `Path(__file__).parent.parent.parent / ".env"` i.e. project root. If running uvicorn from a different directory, the env file won't be found.
- Database health check in the `/health` endpoint is stubbed (`"no_checked"`).
- Agent orchestration (LangGraph), LLM providers (Ollama), and tools (web search, Python executor) are all planned but not yet implemented.
