# Data Agent

**Source**: `app/core/agents/data.py`

## State

| Field | Type |
|-------|------|
| `task` | `str` |
| `context` | `str` |
| `code` | `Optional[str]` |
| `query` | `Optional[str]` |
| `execution_result` | `Optional[dict]` |
| `error` | `Optional[str]` |
| `iteration` | `int` |
| `analysis` | `Optional[str]` |
| `trace_id` | `str` |

## Flow Diagram

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;

    execute_python("⚙ execute_python")
    analyze_task("⚙ analyze_task")
    generate_code("🤖 generate_code")
    execute_sql("⚙ execute_sql")
    classify_output("⚙ classify_output")

    __start__(["Start"]):::first --> analyze_task;
    analyze_task --> generate_code;
    classify_output -. &nbsp;failed&nbsp; .-> __end__(["End"]):::last;
    classify_output -. &nbsp;both&nbsp; .-> execute_python;
    classify_output -. &nbsp;sql&nbsp; .-> execute_sql;
    execute_python -. &nbsp;failed&nbsp; .-> __end__(["End"]):::last;
    execute_python -. &nbsp;sql_pending&nbsp; .-> execute_sql;
    execute_python -. &nbsp;retry&nbsp; .-> generate_code;
    execute_sql -. &nbsp;failed&nbsp; .-> __end__(["End"]):::last;
    execute_sql -. &nbsp;retry&nbsp; .-> generate_code;
    generate_code --> classify_output;

    class execute_python,analyze_task,execute_sql,classify_output defaultNode;
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
| `execute_python` | `generate_code` | `retry` | conditional |
| `execute_sql` | `END` | `failed` | conditional |
| `execute_sql` | `generate_code` | `retry` | conditional |
| `generate_code` | `classify_output` | `—` | direct |
