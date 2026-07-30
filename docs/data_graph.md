# Data Agent

**Source**: `app/core/agents/data.py`

## State

| Field | Type |
|-------|------|
| `task` | `str` |
| `context` | `str` |
| `code` | `str | None` |
| `query` | `str | None` |
| `execution_result` | `dict | None` |
| `error` | `str | None` |
| `iteration` | `int` |
| `analysis` | `str | None` |
| `reflection` | `str | None` |
| `trace_id` | `str` |

## Flow Diagram

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;

    analyze_task("⚙ analyze_task")
    execute_python("⚙ execute_python")
    generate_code("🤖 generate_code")
    reflect_error("⚙ reflect_error")
    classify_output("⚙ classify_output")
    execute_sql("⚙ execute_sql")

    __start__(["Start"]):::first --> analyze_task;
    analyze_task --> generate_code;
    classify_output -. &nbsp;failed&nbsp; .-> __end__(["End"]):::last;
    classify_output -. &nbsp;both&nbsp; .-> execute_python;
    classify_output -. &nbsp;sql&nbsp; .-> execute_sql;
    execute_python -. &nbsp;failed&nbsp; .-> __end__(["End"]):::last;
    execute_python -. &nbsp;sql_pending&nbsp; .-> execute_sql;
    execute_python -. &nbsp;retry&nbsp; .-> reflect_error;
    execute_sql -. &nbsp;failed&nbsp; .-> __end__(["End"]):::last;
    execute_sql -. &nbsp;retry&nbsp; .-> reflect_error;
    generate_code --> classify_output;
    reflect_error --> generate_code;

    class analyze_task,execute_python,reflect_error,classify_output,execute_sql defaultNode;
    class generate_code llmNode;
    classDef first fill-opacity:0;
    classDef last fill:#bfb6fc;
    classDef llmNode fill:#2196f3,stroke:#333,stroke-width:2px,color:#fff;
    classDef defaultNode fill:#607d8b,stroke:#333,stroke-width:2px,color:#fff;
```

## Nodes

| Node | Function | Type | Description |
|------|----------|------|-------------|
| `analyze_task` | `analyze_task()` | default | Decides which tool to use for the task. |
| `generate_code` | `generate_code()` | llm | Generates Python or SQL code based on the analysis. |
| `classify_output` | `classify_output()` | default | Classifies generated code as Python, SQL, or both, and splits if needed. |
| `reflect_error` | `reflect_error()` | default | Analyzes the error and produces a reflection/fix plan. |
| `execute_python` | `execute_python()` | default | Execute the generated Python code. |
| `execute_sql` | `execute_sql()` | default | Execute the generated SQL query. |

## Edges

| From | To | Condition | Type |
|------|----|-----------|------|
| `START` | `analyze_task` | `—` | direct |
| `analyze_task` | `generate_code` | `—` | direct |
| `classify_output` | `END` | `failed` | conditional |
| `classify_output` | `execute_python` | `both` | conditional |
| `classify_output` | `execute_sql` | `sql` | conditional |
| `execute_python` | `END` | `failed` | conditional |
| `execute_python` | `execute_sql` | `sql_pending` | conditional |
| `execute_python` | `reflect_error` | `retry` | conditional |
| `execute_sql` | `END` | `failed` | conditional |
| `execute_sql` | `reflect_error` | `retry` | conditional |
| `generate_code` | `classify_output` | `—` | direct |
| `reflect_error` | `generate_code` | `—` | direct |
