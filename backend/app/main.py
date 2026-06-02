from fastapi import FastAPI

app = FastAPI(title="Atlas Research System", version="0.1.0")


@app.get("/")
async def root():
    return {"message": "Hello from AI Research System"}


@app.get("/health")
async def health():
    return {"status": "ok"}
