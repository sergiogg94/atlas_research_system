from fastapi import FastAPI
from app.api.routes import health

app = FastAPI(title="Atlas Research System", version="0.1.0")

app.include_router(health.router, prefix="/api/v1", tags=["health"])


@app.get("/")
async def root():
    return {"message": "Hello from AI Research System"}
