from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    system: str | None = Field(None, max_length=2000)


class GenerateResponse(BaseResponse):
    provider: str
    response: str


class ModelsResponse(BaseResponse):
    provider: str
    models: list[str]
