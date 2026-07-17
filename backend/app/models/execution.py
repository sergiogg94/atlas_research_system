import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime_utils import now


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    trace_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ExecutionStatus] = mapped_column(
        SQLEnum(ExecutionStatus),
        default=ExecutionStatus.PENDING,
        index=True,
        nullable=False,
    )
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trace_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    step_type = Column(String(50), nullable=True)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    status = Column(String(20), default="completed")
    error = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now)


class ExecutionMetricsCache(Base):
    __tablename__ = "execution_metrics_cache"

    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    trace_id = Column(String(36), nullable=False, unique=True, index=True)
    total_duration_ms = Column(Integer, nullable=True)
    total_llm_calls = Column(Integer, default=0)
    total_tool_calls = Column(Integer, default=0)
    total_steps = Column(Integer, default=0)
    total_tokens_input = Column(Integer, default=0)
    total_tokens_output = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    avg_step_latency_ms = Column(Float, nullable=True)
    avg_llm_latency_ms = Column(Float, nullable=True)
    error_count = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    trace_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    prompt_preview = Column(String(500), nullable=True)
    system_prompt = Column(Text, nullable=True)
    user_prompt = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    model = Column(String(100), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    estimated_tokens_input = Column(Integer, nullable=True)
    estimated_tokens_output = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now)


class ToolCallRecord(Base):
    __tablename__ = "tool_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("execution_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    trace_id = Column(String(36), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False)
    input = Column(JSON, nullable=True)
    output_preview = Column(String(500), nullable=True)
    status = Column(String(20), default="success")
    error = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now)
