from typing import Optional, TypedDict
from uuid import uuid4

from app.core.agents.data import build_data_graph
from app.core.agents.planner import build_planner_graph
from app.core.agents.research import build_research_graph
from app.core.agents.synthesis import build_synthesis_graph
from app.core.llm.factory import get_llm_provider
from app.core.logging import logger
from app.core.state_manager import state_manager
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
    trace_id: str


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


async def run_planner(state: OrchestratorState) -> OrchestratorState:
    """Invoke the Planner Agent to break down the task."""
    if state.get("error"):
        return state

    logger.info("Orchestrator: running planner agent")
    graph = build_planner_graph()
    result = await graph.ainvoke(
        {
            "task_description": state["task_description"],
        }
    )

    if result.get("error"):
        return {**state, "error": f"Planner failed: {result['error']}"}

    plan = result["plan"].model_dump()

    state = await save_checkpoint(
        {
            **state,
            "plan": plan,
            "objective": plan.get("objective", ""),
            "plan_steps": plan.get("steps", []),
            "current_agent": "planner",
            "total_steps": state.get("total_steps", 0) + 1,
        }
    )

    return state


@with_checkpoint
async def run_research(state: OrchestratorState) -> OrchestratorState:
    """Invoke the Research Agent with the plan steps."""
    if state.get("error") or not state.get("plan_steps"):
        return state

    logger.info("Orchestrator: running research agent")
    graph = build_research_graph()
    result = await graph.ainvoke(
        {
            "objective": state["objective"],
            "steps": state["plan_steps"],
            "current_step": 0,
            "findings": [],
        }
    )

    return {
        **state,
        "research_findings": result.get("findings", []),
        "current_agent": "research",
        "total_steps": state.get("total_steps", 0) + len(state.get("plan_steps", [])),
    }


@with_checkpoint
async def run_data(state: OrchestratorState) -> OrchestratorState:
    """Invoke Data Agent if the plan includes data analysis."""
    if state.get("error"):
        return state

    needs_data = _check_if_data_needed(state)
    if not needs_data:
        logger.info("Orchestrator: skipping data agent (not needed)")
        return state

    logger.info("Orchestrator: running data agent")
    graph = build_data_graph()
    result = await graph.ainvoke(
        {
            "task": state["objective"],
            "context": _build_data_context(state),
            "iteration": 0,
        }
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


@with_checkpoint
async def run_synthesis(state: OrchestratorState) -> OrchestratorState:
    """Invoke Synthesis Agent with all results."""
    logger.info("Orchestrator: running synthesis agent")
    graph = build_synthesis_graph()
    result = await graph.ainvoke(
        {
            "objective": state["objective"],
            "task_description": state["task_description"],
            "plan": state.get("plan"),
            "research_findings": state.get("research_findings"),
            "data_results": state.get("data_results"),
        }
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

    logger.info(
        "Orchestrator: re-planning after error in %s: %s",
        state.get("current_agent"),
        state.get("error"),
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
        return {
            **state,
            "error": None,
            "current_agent": next_agent,
            "consecutive_failures": 0,
            "last_failure_agent": None,
        }
    elif decision == "retry":
        same_agent = state.get("last_failure_agent") == state.get("current_agent")
        return {
            **state,
            "error": None,
            "consecutive_failures": (
                state.get("consecutive_failures", 0) + 1 if same_agent else 1
            ),
            "last_failure_agent": state.get("current_agent"),
        }
    return state  # abort — keep error


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
    if state.get("consecutive_failures", 0) >= DEGRADATION_THRESHOLD:
        logger.warning(
            "Degradation detected: %d consecutive failures on agent '%s'",
            state["consecutive_failures"],
            state.get("current_agent", "?"),
        )
        return {
            **state,
            "error": (
                f"Aborting after {state['consecutive_failures']} consecutive failures "
                f"on agent '{state.get('current_agent', '?')}'"
            ),
        }
    return state


async def check_max_steps(state: OrchestratorState) -> OrchestratorState:
    """Prevents infinite loops by stopping at MAX_TOTAL_STEPS."""
    if state.get("total_steps", 0) >= MAX_TOTAL_STEPS:
        logger.warning("Max steps reached (%d)", MAX_TOTAL_STEPS)
        return {**state, "error": f"Execution limit reached: {MAX_TOTAL_STEPS} steps"}
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
