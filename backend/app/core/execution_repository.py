import uuid

from sqlalchemy import case, desc, func, select
from sqlalchemy.dialects.postgresql import insert

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
        status: ExecutionStatus | None = None,
        objective: str | None = None,
        total_steps: int | None = None,
        error: str | None = None,
        report: str | None = None,
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

    async def get_execution_by_trace_id(self, trace_id: str) -> Execution | None:
        async with SessionLocal() as session:
            result = await session.execute(select(Execution).where(Execution.trace_id == trace_id))
            return result.scalar_one_or_none()

    async def get_execution_by_id(self, execution_id: uuid.UUID) -> Execution | None:
        async with SessionLocal() as session:
            return await session.get(Execution, execution_id)

    async def list_executions(
        self, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> tuple[list[Execution], int]:
        async with SessionLocal() as session:
            query = select(Execution)
            if status:
                query = query.where(Execution.status == status)
            query = query.order_by(desc(Execution.created_at))

            count_query = select(func.count()).select_from(Execution)
            if status:
                count_query = count_query.where(Execution.status == status)
            total = int((await session.execute(count_query)).scalar() or 0)

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

    async def compute_and_upsert_metrics(self, execution_id: uuid.UUID) -> ExecutionMetricsCache:
        async with SessionLocal() as session:
            execution = await session.get(Execution, execution_id)
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")

            steps_result = await session.execute(
                select(
                    func.count().label("total_steps"),
                    func.avg(ExecutionStep.latency_ms).label("avg_latency"),
                    func.sum(case((ExecutionStep.status == "failed", 1), else_=0)).label(
                        "error_count"
                    ),
                ).where(ExecutionStep.execution_id == execution_id)
            )
            steps_row = steps_result.one()

            llm_result = await session.execute(
                select(
                    func.count().label("total_calls"),
                    func.coalesce(func.sum(LLMCall.estimated_tokens_input), 0).label(
                        "total_tokens_in"
                    ),
                    func.coalesce(func.sum(LLMCall.estimated_tokens_output), 0).label(
                        "total_tokens_out"
                    ),
                    func.avg(LLMCall.latency_ms).label("avg_latency"),
                ).where(LLMCall.execution_id == execution_id)
            )
            llm_row = llm_result.one()

            tool_result = await session.execute(
                select(func.count()).where(ToolCallRecord.execution_id == execution_id)
            )
            total_tool_calls = tool_result.scalar() or 0

            total_duration = None
            if execution.started_at and execution.completed_at:
                total_duration = int(
                    (execution.completed_at - execution.started_at).total_seconds() * 1000
                )

            stmt = (
                insert(ExecutionMetricsCache)
                .values(
                    execution_id=execution_id,
                    trace_id=execution.trace_id,
                    total_duration_ms=total_duration,
                    total_llm_calls=llm_row.total_calls or 0,
                    total_tool_calls=total_tool_calls,
                    total_steps=steps_row.total_steps or 0,
                    total_tokens_input=llm_row.total_tokens_in or 0,
                    total_tokens_output=llm_row.total_tokens_out or 0,
                    estimated_cost_usd=0.0,
                    avg_step_latency_ms=steps_row.avg_latency,
                    avg_llm_latency_ms=llm_row.avg_latency,
                    error_count=steps_row.error_count or 0,
                )
                .on_conflict_do_update(
                    constraint="execution_metrics_cache_pkey",
                    set_={
                        "trace_id": execution.trace_id,
                        "total_duration_ms": total_duration,
                        "total_llm_calls": llm_row.total_calls or 0,
                        "total_tool_calls": total_tool_calls,
                        "total_steps": steps_row.total_steps or 0,
                        "total_tokens_input": llm_row.total_tokens_in or 0,
                        "total_tokens_output": llm_row.total_tokens_out or 0,
                        "estimated_cost_usd": 0.0,
                        "avg_step_latency_ms": steps_row.avg_latency,
                        "avg_llm_latency_ms": llm_row.avg_latency,
                        "error_count": steps_row.error_count or 0,
                        "updated_at": now(),
                    },
                )
                .returning(ExecutionMetricsCache)
            )
            result = await session.execute(stmt)
            await session.commit()
            metrics = result.scalar_one()
            logger.info("Computed and cached metrics for execution %s", execution_id)
            return metrics

    async def get_metrics(self, trace_id: str) -> ExecutionMetricsCache | None:
        async with SessionLocal() as session:
            result = await session.execute(
                select(ExecutionMetricsCache).where(ExecutionMetricsCache.trace_id == trace_id)
            )
            return result.scalar_one_or_none()


execution_repository = ExecutionRepository()
