import uuid
from datetime import datetime
from enum import Enum

from app.core.database import Base
from sqlalchemy import JSON, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Execution(Base):
    __tablename__ = "executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(36), unique=True, nullable=False, index=True)
    task_description = Column(Text, nullable=False)
    objective = Column(Text, nullable=True)
    status = Column(
        SQLEnum(ExecutionStatus), default=ExecutionStatus.PENDING, index=True
    )
    total_steps = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    report = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


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
    created_at = Column(DateTime, default=datetime.now)


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
    created_at = Column(DateTime, default=datetime.now)


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
    created_at = Column(DateTime, default=datetime.now)
