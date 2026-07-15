from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class DataRequest(BaseModel):
    task: str = Field(..., min_length=10, max_length=2000)
    context: str = Field("", max_length=5000)
    max_iterations: int = Field(3, ge=1, le=5)


class DataResponse(BaseResponse):
    task: str
    code: str | None
    query: str | None
    result: dict | None
    error: str | None
    iterations: int
