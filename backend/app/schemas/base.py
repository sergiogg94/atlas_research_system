from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


## Response base models
class BaseResponse(BaseModel):
    """Base model response for all API endpoints."""

    status: str = Field("success", description="Status of the API response")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )


class BaseResponseWithMetadata(BaseResponse):
    """Base response model that includes a data field for successful responses."""

    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class ErrorResponse(BaseModel):
    """Model for error responses."""

    status: str = Field(default="error", description="Response status")
    error_code: str = Field(
        ..., description="Error code", json_schema_extra={"example": "VALIDATION_ERROR"}
    )
    message: str = Field(
        ..., description="Error message", json_schema_extra={"example": "Invalid input"}
    )
    details: Optional[dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )
