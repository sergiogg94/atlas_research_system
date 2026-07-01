from contextlib import asynccontextmanager

from app.api.routes import data, health, llm, orchestrator, plan, research
from app.core.logging import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Atlas Research System")
    yield
    logger.info("Shutting down Atlas Research System")


app = FastAPI(title="Atlas Research System", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(llm.router, prefix="/api/v1", tags=["llm"])
app.include_router(plan.router, prefix="/api/v1", tags=["plan"])
app.include_router(research.router, prefix="/api/v1", tags=["research"])
app.include_router(data.router, prefix="/api/v1", tags=["data"])
app.include_router(orchestrator.router, prefix="/api/v1", tags=["orchestrator"])

logger.info(
    "Routers registered: /api/v1/health, /api/v1/llm, /api/v1/plan, /api/v1/data"
)


@app.get("/")
async def root():
    return {"message": "Hello from AI Research System"}
