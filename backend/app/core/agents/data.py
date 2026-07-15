import json
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.core.llm.factory import get_llm_provider
from app.core.logging import logger
from app.core.prompts import get_prompt
from app.core.tools import get_tool


class DataState(TypedDict):
    task: str  # Description of the data task
    context: str  # Context from previous research
    code: str | None  # Generated Python code
    query: str | None  # SQL query
    execution_result: dict | None
    error: str | None
    iteration: int  # Iteration counter (max 3)
    analysis: str | None  # Result of the analysis
    trace_id: str


async def analyze_task(state: DataState) -> DataState:
    """Decides which tool to use for the task."""
    if state.get("error"):
        logger.debug("analyze_task skipped due to prior error: %s", state.get("error"))
        return state

    logger.info("Analyzing the task to decide which tool to use")
    provider = get_llm_provider()
    system_prompt = get_prompt("data_analysis_system")
    user_prompt = get_prompt("data_analysis_user")

    response = await provider.generate(
        prompt=user_prompt.format(task=state["task"], context=state.get("context", "")),
        system=system_prompt.template,
    )

    return {**state, "analysis": response}


async def generate_code(state: DataState) -> DataState:
    """Generates Python or SQL code based on the analysis."""
    logger.info("Generating code for the task")
    provider = get_llm_provider()
    user_prompt = get_prompt("data_code_gen_user")
    system_prompt = get_prompt("data_code_gen_system")

    response = await provider.generate(
        prompt=user_prompt.format(
            task=state["task"],
            analysis=state.get("analysis", ""),
            error=state.get("error", "None"),
        ),
        system=system_prompt.template,
    )

    return {**state, "code": response}


async def classify_output(state: DataState) -> DataState:
    """Classifies generated code as Python, SQL, or both, and splits if needed."""
    if not state.get("code"):
        logger.debug("No code to classify")
        return state

    logger.info("Classifying generated output")
    provider = get_llm_provider()
    system_prompt = get_prompt("data_classify_output_system")
    user_prompt = get_prompt("data_classify_output_user")

    response = await provider.generate(
        prompt=user_prompt.format(code=state["code"]),
        system=system_prompt.template,
    )

    try:
        parsed = json.loads(response.strip())
        code_type = parsed.get("type", "python")
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse classify output: %s, defaulting to python", e)
        return {**state, "query": None}

    if code_type == "sql":
        return {**state, "code": None, "query": parsed.get("sql_query")}
    elif code_type == "both":
        return {
            **state,
            "code": parsed.get("python_code"),
            "query": parsed.get("sql_query"),
        }

    return {**state, "code": parsed.get("python_code") or state["code"], "query": None}


async def execute_python(state: DataState) -> DataState:
    """Execute the generated Python code."""
    if not state.get("code"):
        logger.debug("No code provided for python execution node")
        return state

    logger.info("Executing python code")
    tool = get_tool("python_executor")
    result = await tool.execute(code=state["code"])

    return {
        **state,
        "execution_result": result.data if result.success else None,
        "error": result.error if not result.success else None,
        "iteration": state.get("iteration", 0) + 1,
    }


async def execute_sql(state: DataState) -> DataState:
    """Execute the generated SQL query."""
    if not state.get("query"):
        logger.debug("No query provided for SQL execution node")
        return state

    logger.info("Executing SQL query")
    tool = get_tool("sql_query")
    result = await tool.execute(query=state["query"])

    return {
        **state,
        "execution_result": result.data if result.success else None,
        "error": result.error if not result.success else None,
        "iteration": state.get("iteration", 0) + 1,
    }


def route_execution(state: DataState) -> str:
    """Routes to the correct execution node based on actual generated content."""
    has_python = bool(state.get("code"))
    has_sql = bool(state.get("query"))

    if has_python and has_sql:
        return "both"
    if has_sql:
        return "sql"
    if has_python:
        return "python_only"
    return "failed"


def has_python_error(state: DataState) -> str:
    """Error check for Python execution; may route to SQL if query is pending."""
    if state.get("error") and state.get("iteration", 0) < 3:
        return "retry"
    if state.get("error"):
        return "failed"
    if state.get("query"):
        return "sql_pending"
    return "success"


def has_sql_error(state: DataState) -> str:
    """Error check for SQL execution."""
    if state.get("error") and state.get("iteration", 0) < 3:
        return "retry"
    if state.get("error"):
        return "failed"
    return "success"


def build_data_graph() -> StateGraph:
    logger.info("Building data StateGraph")
    workflow = StateGraph(DataState)

    workflow.add_node("analyze_task", analyze_task)
    workflow.add_node("generate_code", generate_code)
    workflow.add_node("classify_output", classify_output)
    workflow.add_node("execute_python", execute_python)
    workflow.add_node("execute_sql", execute_sql)

    workflow.set_entry_point("analyze_task")

    workflow.add_edge("analyze_task", "generate_code")
    workflow.add_edge("generate_code", "classify_output")

    workflow.add_conditional_edges(
        "classify_output",
        route_execution,
        {
            "python_only": "execute_python",
            "sql": "execute_sql",
            "both": "execute_python",
            "failed": END,
        },
    )

    workflow.add_conditional_edges(
        "execute_python",
        has_python_error,
        {
            "retry": "generate_code",
            "sql_pending": "execute_sql",
            "success": END,
            "failed": END,
        },
    )

    workflow.add_conditional_edges(
        "execute_sql",
        has_sql_error,
        {
            "retry": "generate_code",
            "success": END,
            "failed": END,
        },
    )

    try:
        compiled = workflow.compile()
        logger.info("Data StateGraph compiled successfully")
        return compiled
    except Exception as e:
        logger.exception("Failed to compile data StateGraph: %s", e)
        raise
