from app.schemas.base import BaseResponse
from pydantic import BaseModel, Field
from typing import Optional


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    system: Optional[str] = Field(None, max_length=2000)


class GenerateResponse(BaseResponse):
    provider: str
    response: str


class ModelsResponse(BaseResponse):
    provider: str
    models: list[str]
