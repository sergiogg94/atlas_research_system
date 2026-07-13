import uuid
from typing import Optional

from app.core.database import SessionLocal
from app.core.datetime_utils import now
from app.core.logging import logger
from app.models.execution import (
    Execution,
    ExecutionMetricsCache,
    ExecutionStatus,
    ExecutionStep,
    LLMCall,
    ToolCallRecord,
)
from sqlalchemy import desc, func, select


class ExecutionRepository:
    """Repository for persisting and querying execution history."""

    async def create_execution(
        self, trace_id: str, task_description: str, objective: str = ""
    ) -> Execution:
        """Create a new execution record in the database."""
        async with SessionLocal() as session:
            execution = Execution(
                id=uuid.uuid4(),
                trace_id=trace_id,
                task_description=task_description,
                objective=objective,
                status=ExecutionStatus.RUNNING,
                started_at=now(),
            )
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            logger.info("Created new execution with ID: %s", execution.id)

            return execution

    async def update_execution(
        self,
        execution_id: uuid.UUID,
        status: Optional[ExecutionStatus] = None,
        objective: Optional[str] = None,
        total_steps: Optional[int] = None,
        error: Optional[str] = None,
        report: Optional[str] = None,
    ) -> None:
        """Update an existing execution record in the database."""
        async with SessionLocal() as session:
            execution = await session.get(Execution, execution_id)
            if not execution:
                logger.error("Execution with ID %s not found", execution_id)
                return

            if status:
                execution.status = status
            if objective is not None:
                execution.objective = objective
            if total_steps is not None:
                execution.total_steps = total_steps
            if error is not None:
                execution.error = error
            if report is not None:
                execution.report = report
            if status in [
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.TIMEOUT,
            ]:
                execution.completed_at = now()

            execution.updated_at = now()

            await session.commit()
            await session.refresh(execution)
            logger.debug("Updated execution with ID: %s", execution.id)

    async def add_step(self, step_data: dict) -> ExecutionStep:
        async with SessionLocal() as session:
            step = ExecutionStep(id=uuid.uuid4(), **step_data)
            session.add(step)
            await session.commit()
            await session.refresh(step)
            return step

    async def add_llm_call(self, call_data: dict) -> LLMCall:
        async with SessionLocal() as session:
            call = LLMCall(id=uuid.uuid4(), **call_data)
            session.add(call)
            await session.commit()
            await session.refresh(call)
            return call

    async def add_tool_call(self, call_data: dict) -> ToolCallRecord:
        async with SessionLocal() as session:
            record = ToolCallRecord(id=uuid.uuid4(), **call_data)
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    ###########################################################################
    # Query Methods
    ###########################################################################

    async def get_execution_by_trace_id(self, trace_id: str) -> Optional[Execution]:
        async with SessionLocal() as session:
            result = await session.execute(
                select(Execution).where(Execution.trace_id == trace_id)
            )
            return result.scalar_one_or_none()

    async def get_execution_by_id(self, execution_id: uuid.UUID) -> Optional[Execution]:
        async with SessionLocal() as session:
            return await session.get(Execution, execution_id)

    async def list_executions(
        self, page: int = 1, page_size: int = 20, status: Optional[str] = None
    ) -> tuple[list[Execution], int]:
        async with SessionLocal() as session:
            query = select(Execution)
            if status:
                query = query.where(Execution.status == status)
            query = query.order_by(desc(Execution.created_at))

            count_query = select(func.count()).select_from(Execution)
            if status:
                count_query = count_query.where(Execution.status == status)
            total = (await session.execute(count_query)).scalar()

            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(query)
            return list(result.scalars().all()), total

    async def get_steps(self, execution_id: uuid.UUID) -> list[ExecutionStep]:
        async with SessionLocal() as session:
            result = await session.execute(
                select(ExecutionStep)
                .where(ExecutionStep.execution_id == execution_id)
                .order_by(ExecutionStep.created_at)
            )
            return list(result.scalars().all())

    async def get_llm_calls(self, execution_id: uuid.UUID) -> list[LLMCall]:
        async with SessionLocal() as session:
            result = await session.execute(
                select(LLMCall)
                .where(LLMCall.execution_id == execution_id)
                .order_by(LLMCall.created_at)
            )
            return list(result.scalars().all())

    async def get_tool_calls(self, execution_id: uuid.UUID) -> list[ToolCallRecord]:
        async with SessionLocal() as session:
            result = await session.execute(
                select(ToolCallRecord)
                .where(ToolCallRecord.execution_id == execution_id)
                .order_by(ToolCallRecord.created_at)
            )
            return list(result.scalars().all())

    async def get_metrics(
        self, trace_id: str
    ) -> Optional[ExecutionMetricsCache]:
        async with SessionLocal() as session:
            result = await session.execute(
                select(ExecutionMetricsCache).where(
                    ExecutionMetricsCache.trace_id == trace_id
                )
            )
            return result.scalar_one_or_none()


execution_repository = ExecutionRepository()
