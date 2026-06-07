from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, llm

app = FastAPI(title="Atlas Research System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(llm.router, prefix="/api/v1", tags=["llm"])


@app.get("/")
async def root():
    return {"message": "Hello from AI Research System"}
