from typing import Optional, TypedDict
from uuid import UUID, uuid4

from app.core.agents.data import build_data_graph
from app.core.agents.planner import build_planner_graph
from app.core.agents.research import build_research_graph
from app.core.agents.synthesis import build_synthesis_graph
from app.core.execution_repository import execution_repository
from app.core.llm.factory import get_llm_provider
from app.core.logging import (
    execution_id_var,
    logger,
    step_id_var,
    trace_context,
    trace_step,
)
from app.core.state_manager import state_manager
from app.models.execution import ExecutionStatus
from langgraph.graph import END, StateGraph


class OrchestratorState(TypedDict):
    task_description: str  # Originl input
    objective: str  # From plam
    plan: Optional[dict]  # Planner's output
    plan_steps: Optional[list]  # Plan steps
    research_findings: Optional[list]  # Research Output
    data_results: Optional[list]  # Data Output
    report: Optional[str]  # Synthesis Output
    error: Optional[str]
    current_agent: str  # "planner" | "research" | "data" | "synthesis"
    step_index: int  # Current step index
    total_steps: int  # Total of executed steps
    max_steps: int  # Scecurity limit
    checkpoint_idx: Optional[str]  # Redis checkpoint id
    consecutive_failures: int  # Degradation detection
    last_failure_agent: Optional[str]  # Last agent that failed
    trace_id: str  # Unique trace id for logging and tracing
    execution_id: Optional[str]  # Database execution ID
    last_step_latency_ms: Optional[int]  # Latency of last step in milliseconds


MAX_TOTAL_STEPS = 50
DEGRADATION_THRESHOLD = 3
AGENT_ORDER = ["planner", "research", "data", "synthesis"]


async def save_checkpoint(state: OrchestratorState) -> OrchestratorState:
    """Persists the current state in Redis"""
    checkpoint_idx = state.get("checkpoint_idx") or str(uuid4())

    # Asegurar que todo sea JSON-serializable
    clean_state = _sanitize_for_json(dict(state))

    try:
        await state_manager.save_orchestrator_state(checkpoint_idx, clean_state)
    except Exception as e:
        logger.error("Failed to save checkpoint: %s", e)
        return {**state, "error": f"Checkpoint save failed: {e}"}

    return {**state, "checkpoint_idx": checkpoint_idx}


def _sanitize_for_json(obj: dict) -> dict:
    """Recursively converts non-JSON-serializable objects to strings/dicts"""
    import json

    try:
        # Intentar serializar - si falla, sanitizar
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        pass

    # Limpiar recursivamente
    cleaned = {}
    for key, value in obj.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        elif isinstance(value, dict):
            cleaned[key] = _sanitize_for_json(value)
        elif isinstance(value, (list, tuple)):
            cleaned[key] = [
                (
                    _sanitize_for_json(item)
                    if isinstance(item, dict)
                    else (
                        str(item)
                        if not isinstance(item, (str, int, float, bool))
                        else item
                    )
                )
                for item in value
            ]
        else:
            # Objetos no serializables → convertir a string
            cleaned[key] = str(value)

    return cleaned


def with_checkpoint(node_func):
    """Wrapper that persists state after each node."""

    async def wrapped(state):
        result = await node_func(state)
        if result.get("checkpoint_idx"):
            await state_manager.save_orchestrator_state(
                result["checkpoint_idx"], dict(result)
            )
        return result

    return wrapped


async def _record_execution_step(
    state: OrchestratorState,
    agent_name: str,
    step_type: str,
    input_summary: Optional[str] = None,
    output_summary: Optional[str] = None,
    status: str = "completed",
    error: Optional[str] = None,
    latency_ms: Optional[int] = None,
):
    """Persist a step record for the current execution when an execution_id exists."""
    execution_id = state.get("execution_id")
    if not execution_id:
        return None

    try:
        execution_uuid = (
            execution_id if isinstance(execution_id, UUID) else UUID(str(execution_id))
        )
    except ValueError:
        logger.warning(
            "Invalid execution_id received for step recording: %s", execution_id
        )
        return None

    try:
        return await execution_repository.add_step(
            {
                "execution_id": execution_uuid,
                "trace_id": state.get("trace_id", ""),
                "agent_name": agent_name,
                "step_type": step_type,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "status": status,
                "error": error,
                "latency_ms": latency_ms,
            }
        )
    except Exception as exc:
        logger.warning("Failed to record execution step for %s: %s", agent_name, exc)
        return None


@trace_step("planner")
async def run_planner(state: OrchestratorState) -> OrchestratorState:
    """Invoke the Planner Agent to break down the task."""
    if state.get("error"):
        return state

    with trace_context(state.get("trace_id", ""), "planner"):
        logger.info("Orchestrator: running planner agent")

        execution = await execution_repository.create_execution(
            trace_id=state.get("trace_id", ""),
            task_description=state.get("task_description", ""),
            objective=state.get("objective", ""),
        )
        execution_state = {
            **state,
            "execution_id": str(execution.id),
        }

        execution_id_var.set(str(execution.id))

        step = await _record_execution_step(
            execution_state,
            agent_name="planner",
            step_type="planning",
            input_summary=state.get("task_description"),
            status="running",
        )
        if step:
            step_id_var.set(str(step.id))

        graph = build_planner_graph()
        try:
            result = await graph.ainvoke(
                {
                    "task_description": state["task_description"],
                }
            )
        except Exception as exc:
            await execution_repository.update_execution(
                execution_id=execution.id,
                status=ExecutionStatus.FAILED,
                error=str(exc),
            )
            await _record_execution_step(
                execution_state,
                agent_name="planner",
                step_type="planning",
                input_summary=state.get("task_description"),
                output_summary=str(exc),
                status="failed",
                error=str(exc),
            )
            return {**state, "error": f"Planner failed: {exc}"}

        if result.get("error"):
            await execution_repository.update_execution(
                execution_id=execution.id,
                status=ExecutionStatus.FAILED,
                error=str(result["error"]),
            )
            await _record_execution_step(
                execution_state,
                agent_name="planner",
                step_type="planning",
                input_summary=state.get("task_description"),
                output_summary=str(result["error"]),
                status="failed",
                error=str(result["error"]),
            )
            return {**state, "error": f"Planner failed: {result['error']}"}

        plan = result["plan"].model_dump()

        await _record_execution_step(
            execution_state,
            agent_name="planner",
            step_type="planning",
            input_summary=state.get("task_description"),
            output_summary=str(plan.get("objective", "")),
            status="completed",
            latency_ms=state.get("last_step_latency_ms"),
        )

        state = await save_checkpoint(
            {
                **state,
                "plan": plan,
                "objective": plan.get("objective", ""),
                "plan_steps": plan.get("steps", []),
                "current_agent": "planner",
                "total_steps": state.get("total_steps", 0) + 1,
                "execution_id": str(execution.id),
            }
        )

        await execution_repository.update_execution(
            execution_id=execution.id,
            objective=plan.get("objective", ""),
            total_steps=state.get("total_steps", 0),
        )

        return state


@trace_step("research")
@with_checkpoint
async def run_research(state: OrchestratorState) -> OrchestratorState:
    """Invoke the Research Agent with the plan steps."""
    if state.get("error") or not state.get("plan_steps"):
        return state

    with trace_context(state.get("trace_id", ""), "research"):
        logger.info("Orchestrator: running research agent")

        execution_id_var.set(state.get("execution_id", ""))

        step = await _record_execution_step(
            state,
            agent_name="research",
            step_type="research",
            input_summary=str(state.get("plan_steps", [])),
            status="running",
        )
        if step:
            step_id_var.set(str(step.id))

        graph = build_research_graph()
        try:
            result = await graph.ainvoke(
                {
                    "objective": state["objective"],
                    "steps": state["plan_steps"],
                    "current_step": 0,
                    "findings": [],
                }
            )
        except Exception as exc:
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.FAILED,
                error=str(exc),
            )
            await _record_execution_step(
                state,
                agent_name="research",
                step_type="research",
                input_summary=str(state.get("plan_steps", [])),
                output_summary=str(exc),
                status="failed",
                error=str(exc),
            )
            return {
                **state,
                "error": f"Research failed: {exc}",
                "current_agent": "research",
            }

        if result.get("error"):
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.FAILED,
                error=str(result["error"]),
            )
            await _record_execution_step(
                state,
                agent_name="research",
                step_type="research",
                input_summary=str(state.get("plan_steps", [])),
                output_summary=str(result["error"]),
                status="failed",
                error=str(result["error"]),
            )
            return {
                **state,
                "error": f"Research failed: {result['error']}",
                "current_agent": "research",
            }

        await execution_repository.update_execution(
            execution_id=UUID(state["execution_id"]),
            total_steps=state.get("total_steps", 0) + len(state.get("plan_steps", [])),
        )
        await _record_execution_step(
            state,
            agent_name="research",
            step_type="research",
            input_summary=str(state.get("plan_steps", [])),
            output_summary=str(result.get("findings", [])),
            status="completed",
            latency_ms=state.get("last_step_latency_ms"),
        )

        return {
            **state,
            "research_findings": result.get("findings", []),
            "current_agent": "research",
            "total_steps": state.get("total_steps", 0)
            + len(state.get("plan_steps", [])),
        }


@trace_step("data")
@with_checkpoint
async def run_data(state: OrchestratorState) -> OrchestratorState:
    """Invoke Data Agent if the plan includes data analysis."""
    if state.get("error"):
        return state

    with trace_context(state.get("trace_id", ""), "data"):
        needs_data = _check_if_data_needed(state)
        if not needs_data:
            logger.info("Orchestrator: skipping data agent (not needed)")
            return state

        logger.info("Orchestrator: running data agent")

        execution_id_var.set(state.get("execution_id", ""))

        step = await _record_execution_step(
            state,
            agent_name="data",
            step_type="data_analysis",
            input_summary=state.get("objective"),
            status="running",
        )
        if step:
            step_id_var.set(str(step.id))

        graph = build_data_graph()
        try:
            result = await graph.ainvoke(
                {
                    "task": state["objective"],
                    "context": _build_data_context(state),
                    "iteration": 0,
                }
            )
        except Exception as exc:
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.FAILED,
                error=str(exc),
            )
            await _record_execution_step(
                state,
                agent_name="data",
                step_type="data_analysis",
                input_summary=state.get("objective"),
                output_summary=str(exc),
                status="failed",
                error=str(exc),
            )
            return {
                **state,
                "error": f"Data agent failed: {exc}",
                "current_agent": "data",
            }

        if result.get("error"):
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.FAILED,
                error=str(result["error"]),
            )
            await _record_execution_step(
                state,
                agent_name="data",
                step_type="data_analysis",
                input_summary=state.get("objective"),
                output_summary=str(result["error"]),
                status="failed",
                error=str(result["error"]),
            )
            return {
                **state,
                "error": f"Data agent failed: {result['error']}",
                "current_agent": "data",
            }

        await execution_repository.update_execution(
            execution_id=UUID(state["execution_id"]),
            total_steps=state.get("total_steps", 0) + 1,
        )
        await _record_execution_step(
            state,
            agent_name="data",
            step_type="data_analysis",
            input_summary=state.get("objective"),
            output_summary=str(result.get("execution_result", "")),
            status="completed",
            latency_ms=state.get("last_step_latency_ms"),
        )

        return {
            **state,
            "data_results": result.get("execution_result"),
            "current_agent": "data",
            "total_steps": state.get("total_steps", 0) + 1,
        }


def _check_if_data_needed(state: OrchestratorState) -> bool:
    """Review the plan to determine if Data Agent is required."""
    steps = state.get("plan_steps") or []
    analysis_keywords = [
        "analysis",
        "analyze",
        "calculate",
        "compute",
        "statistics",
        "data",
        "chart",
        "plot",
        "visualize",
    ]
    for step in steps:
        action = (step.get("action") or step.get("step_type") or "").lower()
        if any(kw in action for kw in analysis_keywords):
            return True
    return False


def _build_data_context(state: OrchestratorState) -> str:
    """Generates the context for the Data Agent."""
    parts = [f"# Objective\n{state.get('objective', '')}\n"]

    if state.get("plan"):
        plan = state["plan"]
        parts.append(f"# Plan\n{plan.get('objective', '')}\n")

    findings = state.get("research_findings") or []
    if findings:
        lines = ["# Research Findings\n"]
        for f in findings:
            step = f.get("step", "?")
            query = f.get("query", "")
            summary = f.get("summary", "")
            lines.append(f"## Step {step}")
            if query:
                lines.append(f"Query: {query}")
            lines.append(f"Summary: {summary}")
        parts.append("\n".join(lines))

    context = "\n".join(parts)
    if len(context) > 5000:
        context = context[:5000] + "\n\n[Context truncated...]"
    return context


@trace_step("synthesis")
@with_checkpoint
async def run_synthesis(state: OrchestratorState) -> OrchestratorState:
    """Invoke Synthesis Agent with all results."""
    with trace_context(state.get("trace_id", ""), "synthesis"):
        logger.info("Orchestrator: running synthesis agent")

        execution_id_var.set(state.get("execution_id", ""))

        step = await _record_execution_step(
            state,
            agent_name="synthesis",
            step_type="synthesis",
            input_summary="Combining research and data findings",
            status="running",
        )
        if step:
            step_id_var.set(str(step.id))

        graph = build_synthesis_graph()
        try:
            result = await graph.ainvoke(
                {
                    "objective": state["objective"],
                    "task_description": state["task_description"],
                    "plan": state.get("plan"),
                    "research_findings": state.get("research_findings"),
                    "data_results": state.get("data_results"),
                }
            )
        except Exception as exc:
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.FAILED,
                error=str(exc),
            )
            await _record_execution_step(
                state,
                agent_name="synthesis",
                step_type="synthesis",
                input_summary="Combining research and data findings",
                output_summary=str(exc),
                status="failed",
                error=str(exc),
            )
            return {
                **state,
                "error": f"Synthesis failed: {exc}",
                "current_agent": "synthesis",
            }

        if result.get("error"):
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.FAILED,
                error=str(result["error"]),
            )
            await _record_execution_step(
                state,
                agent_name="synthesis",
                step_type="synthesis",
                input_summary="Combining research and data findings",
                output_summary=str(result["error"]),
                status="failed",
                error=str(result["error"]),
            )
            return {
                **state,
                "error": f"Synthesis failed: {result['error']}",
                "current_agent": "synthesis",
            }

        await execution_repository.update_execution(
            execution_id=UUID(state["execution_id"]),
            status=ExecutionStatus.COMPLETED,
            total_steps=state.get("total_steps", 0) + 1,
            report=result.get("report"),
        )
        await _record_execution_step(
            state,
            agent_name="synthesis",
            step_type="synthesis",
            input_summary="Combining research and data findings",
            output_summary=str(result.get("report", "")),
            status="completed",
            latency_ms=state.get("last_step_latency_ms"),
        )

        return {
            **state,
            "report": result.get("report"),
            "current_agent": "synthesis",
            "total_steps": state.get("total_steps", 0) + 1,
        }


def route_from_planner(state: OrchestratorState) -> str:
    """Determine the next agent after the planner."""
    if state.get("error"):
        return "error"
    return "research"


def route_from_research(state: OrchestratorState) -> str:
    """Determine whether a Data Agent is needed or if you should proceed directly to synthesis."""
    if state.get("error"):
        return "error"
    if _check_if_data_needed(state):
        return "data"
    return "synthesis"


def route_from_data(state: OrchestratorState) -> str:
    """Determine the next agent after the data."""
    if state.get("error"):
        return "error"
    return "synthesis"


async def re_plan(state: OrchestratorState) -> OrchestratorState:
    """If an agent failed, try to re-plan with the LLM."""
    if not state.get("error"):
        return state

    with trace_context(state.get("trace_id", ""), "re_plan"):
        logger.info(
            "Orchestrator: re-planning after error in %s: %s",
            state.get("current_agent"),
            state.get("error"),
        )

        await _record_execution_step(
            state,
            agent_name="orchestrator",
            step_type="re_plan",
            input_summary=f"Agent '{state.get('current_agent')}' failed",
            output_summary=state.get("error"),
            status="running",
        )

        try:
            provider = get_llm_provider()
            prompt = (
                f"The agent '{state.get('current_agent')}' failed with error:\n"
                f"{state.get('error')}\n\n"
                f"Original task: {state.get('task_description')}\n"
                f"Objective: {state.get('objective')}\n\n"
                "Respond in JSON only with this structure:\n"
                '{"decision": "retry"|"skip"|"abort", "reason": "..."}\n'
                '- "retry": re-run the failed agent\n'
                '- "skip": skip the failed agent and continue\n'
                '- "abort": cannot recover, stop'
            )
            response = await provider.generate(
                prompt=prompt,
                system="You are a re-planning assistant. Respond only in JSON.",
            )
            import json

            data = json.loads(response.strip())
            decision = data.get("decision", "abort")
        except Exception:
            logger.warning("Orchestrator: re_plan LLM failed, defaulting to abort")
            decision = "abort"

        if decision == "skip":
            next_agent = _next_agent(state.get("current_agent", ""), state)
            await _record_execution_step(
                state,
                agent_name="orchestrator",
                step_type="re_plan",
                input_summary=f"Skipping failed agent '{state.get('current_agent')}'",
                output_summary=f"Moving to {next_agent}",
                status="completed",
            )
            return {
                **state,
                "error": None,
                "current_agent": next_agent,
                "consecutive_failures": 0,
                "last_failure_agent": None,
            }
        elif decision == "retry":
            same_agent = state.get("last_failure_agent") == state.get("current_agent")
            await _record_execution_step(
                state,
                agent_name="orchestrator",
                step_type="re_plan",
                input_summary=f"Retrying agent '{state.get('current_agent')}'",
                output_summary=f"Attempt {state.get('consecutive_failures', 0) + 1}",
                status="completed",
            )
            return {
                **state,
                "error": None,
                "consecutive_failures": (
                    state.get("consecutive_failures", 0) + 1 if same_agent else 1
                ),
                "last_failure_agent": state.get("current_agent"),
            }
        # abort — keep error
        await _record_execution_step(
            state,
            agent_name="orchestrator",
            step_type="re_plan",
            input_summary=f"Aborting after failure in '{state.get('current_agent')}'",
            output_summary=state.get("error"),
            status="completed",
        )
        return state


def _next_agent(current: str, state: OrchestratorState) -> str:
    """Returns the next agent after `current` in the pipeline."""
    if current not in AGENT_ORDER:
        return "synthesis"
    idx = AGENT_ORDER.index(current)
    if idx >= len(AGENT_ORDER) - 1:
        return "synthesis"
    if current == "research" and not _check_if_data_needed(state):
        return "synthesis"
    return AGENT_ORDER[idx + 1]


def route_after_replan(state: OrchestratorState) -> str:
    """Route after re_plan to the appropriate node."""
    if state.get("error"):
        return "end"
    mapping = {
        "planner": "run_planner",
        "research": "run_research",
        "data": "run_data",
        "synthesis": "run_synthesis",
    }
    return mapping.get(state.get("current_agent", ""), "end")


async def check_degradation(state: OrchestratorState) -> OrchestratorState:
    """Detects degradation: abort after multiple consecutive failures on the same agent."""
    with trace_context(state.get("trace_id", ""), "degradation_check"):
        if state.get("consecutive_failures", 0) >= DEGRADATION_THRESHOLD:
            logger.warning(
                "Degradation detected: %d consecutive failures on agent '%s'",
                state["consecutive_failures"],
                state.get("current_agent", "?"),
            )
            error_msg = (
                f"Aborting after {state['consecutive_failures']} consecutive failures "
                f"on agent '{state.get('current_agent', '?')}'"
            )
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.FAILED,
                error=error_msg,
            )
            await _record_execution_step(
                state,
                agent_name="orchestrator",
                step_type="degradation_check",
                input_summary=f"Consecutive failures: {state.get('consecutive_failures', 0)}",
                output_summary=error_msg,
                status="completed",
            )
            return {
                **state,
                "error": error_msg,
            }
        return state


async def check_max_steps(state: OrchestratorState) -> OrchestratorState:
    """Prevents infinite loops by stopping at MAX_TOTAL_STEPS."""
    with trace_context(state.get("trace_id", ""), "max_steps_check"):
        if state.get("total_steps", 0) >= MAX_TOTAL_STEPS:
            logger.warning("Max steps reached (%d)", MAX_TOTAL_STEPS)
            error_msg = f"Execution limit reached: {MAX_TOTAL_STEPS} steps"
            await execution_repository.update_execution(
                execution_id=UUID(state["execution_id"]),
                status=ExecutionStatus.TIMEOUT,
                error=error_msg,
            )
            await _record_execution_step(
                state,
                agent_name="orchestrator",
                step_type="max_steps_check",
                input_summary=f"Total steps: {state.get('total_steps', 0)}",
                output_summary=error_msg,
                status="completed",
            )
            return {
                **state,
                "error": error_msg,
            }
        return state


def route_after_check(state: OrchestratorState) -> str:
    """Route after the max-steps check to the appropriate next node."""
    if state.get("error"):
        if "limit reached" in state.get("error", ""):
            return "end"
        return "re_plan"

    from_agent = state.get("current_agent", "")
    if from_agent == "planner":
        return route_from_planner(state)
    elif from_agent == "research":
        return route_from_research(state)
    elif from_agent == "data":
        return route_from_data(state)
    return "end"


def build_orchestrator_graph() -> StateGraph:
    logger.info("Building orchestrator graph")
    workflow = StateGraph(OrchestratorState)

    # Add nodes
    workflow.add_node("run_planner", run_planner)
    workflow.add_node("run_research", run_research)
    workflow.add_node("run_data", run_data)
    workflow.add_node("run_synthesis", run_synthesis)
    workflow.add_node("re_plan", re_plan)
    workflow.add_node("check_max_steps", check_max_steps)
    workflow.add_node("check_degradation", check_degradation)

    # Set entry point
    workflow.set_entry_point("run_planner")

    # Define edges — each agent node goes through the max-steps check
    workflow.add_edge("run_planner", "check_max_steps")
    workflow.add_edge("run_research", "check_max_steps")
    workflow.add_edge("run_data", "check_max_steps")

    workflow.add_conditional_edges(
        "check_max_steps",
        route_after_check,
        {
            "research": "run_research",
            "data": "run_data",
            "synthesis": "run_synthesis",
            "error": "re_plan",
            "re_plan": "re_plan",
            "end": END,
        },
    )

    # re_plan → degradation check → route back to an agent or END
    workflow.add_edge("re_plan", "check_degradation")

    workflow.add_conditional_edges(
        "check_degradation",
        route_after_replan,
        {
            "run_planner": "run_planner",
            "run_research": "run_research",
            "run_data": "run_data",
            "run_synthesis": "run_synthesis",
            "end": END,
        },
    )
    workflow.add_edge("run_synthesis", END)

    try:
        compiled = workflow.compile()
        logger.info("Orchestrator StateGraph compiled successfully")
        return compiled
    except Exception as e:
        logger.exception("Failed to compile orchestrator StateGraph: %s", e)
        raise
