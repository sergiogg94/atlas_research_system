import json
from typing import Optional, TypedDict

from app.core.llm.factory import get_llm_provider
from app.core.logging import logger
from app.core.prompts import get_prompt
from app.schemas.plan import Plan
from langgraph.graph import END, StateGraph
from pydantic import ValidationError


class PlannerState(TypedDict):
    task_description: str
    plan: Optional[Plan]
    error: Optional[str]
    llm_response: Optional[str]
    trace_id: str


def validate_task(state: PlannerState) -> PlannerState:
    """Validate that the task description is not empty."""
    logger.info("Validating task: %s", (state.get("task_description") or "")[:200])
    if not state["task_description"] or len(state["task_description"]) < 10:
        logger.warning(
            "Validation failed: %s",
            "Task description must be at least 10 characters",
        )
        return {**state, "error": "Task description must be at least 10 characters"}
    logger.debug("Validation passed for task")
    return state


async def generate_plan(state: PlannerState) -> PlannerState:
    """Call the LLM to generate a plan."""
    if state.get("error"):
        logger.debug("generate_plan skipped due to prior error: %s", state.get("error"))
        return state

    provider = get_llm_provider()
    logger.info(
        "Using LLM provider %s to generate plan",
        getattr(provider, "name", provider.__class__.__name__),
    )
    sys_prompt = get_prompt("planner_system")
    user_prompt = get_prompt("planner_user")

    prompt_text = user_prompt.format(task_description=state["task_description"])
    logger.debug("Generated user prompt (truncated): %s", prompt_text[:500])

    response = await provider.generate(
        prompt=prompt_text,
        system=sys_prompt.template,
    )

    logger.info(
        "LLM generation completed; response_length=%s", len(response) if response else 0
    )
    logger.debug("LLM response preview: %s", (response or "")[:500])

    return {**state, "llm_response": response}


def parse_plan(state: PlannerState) -> PlannerState:
    """Parse and validate the LLM response into a Plan."""
    if state.get("error"):
        logger.debug("parse_plan skipped due to prior error: %s", state.get("error"))
        return state

    try:
        logger.debug(
            "Parsing LLM response (truncated): %s",
            (state.get("llm_response") or "")[:500],
        )
        data = json.loads(state["llm_response"])
        plan = Plan(**data)
        # include a lightweight info about parsed plan when possible
        plan_summary = None
        if hasattr(plan, "steps"):
            try:
                plan_summary = len(getattr(plan, "steps"))
            except Exception:
                plan_summary = None
        logger.info(
            "Plan parsed successfully%s",
            (f"; steps={plan_summary}" if plan_summary is not None else ""),
        )
        return {**state, "plan": plan}
    except (json.JSONDecodeError, ValidationError) as e:
        logger.exception("Failed to parse plan: %s", e)
        return {**state, "error": f"Failed to parse plan: {e}"}


def has_error(state: PlannerState) -> str:
    result = "error" if state.get("error") else "continue"
    logger.debug("has_error -> %s", result)
    return result


def plan_complete(state: PlannerState) -> str:
    if state.get("plan"):
        logger.debug("plan_complete -> complete")
        return "complete"
    if state.get("error"):
        logger.debug("plan_complete -> error")
        return "error"
    logger.debug("plan_complete -> continue")
    return "continue"


def build_planner_graph() -> StateGraph:
    logger.info("Building planner StateGraph")
    workflow = StateGraph(PlannerState)

    # Add nodes
    workflow.add_node("validate", validate_task)
    workflow.add_node("generate", generate_plan)
    workflow.add_node("parse", parse_plan)

    # Set entry point
    workflow.set_entry_point("validate")

    # Add edges
    workflow.add_conditional_edges(
        "validate",
        has_error,
        {"error": END, "continue": "generate"},
    )
    workflow.add_edge("generate", "parse")
    workflow.add_conditional_edges(
        "parse",
        plan_complete,
        {"complete": END, "error": END},
    )

    try:
        compiled = workflow.compile()
        logger.info("Planner StateGraph compiled successfully")
        return compiled
    except Exception as e:
        logger.exception("Failed to compile planner StateGraph: %s", e)
        raise
