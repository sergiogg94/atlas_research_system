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

## Flow Diagram

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;

    analyze_task("⚙ analyze_task")
    generate_code("🤖 generate_code")
    execute_sql("⚙ execute_sql")
    execute_python("⚙ execute_python")

    __start__(["Start"]):::first --> analyze_task;
    analyze_task --> generate_code;
    execute_python -. &nbsp;failed&nbsp; .-> __end__(["End"]):::last;
    execute_python -. &nbsp;retry&nbsp; .-> generate_code;
    generate_code -. &nbsp;python_only&nbsp; .-> execute_python;
    generate_code -. &nbsp;sql&nbsp; .-> execute_sql;
    execute_sql --> __end__(["End"]):::last;

    class analyze_task,execute_sql,execute_python defaultNode;
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
| `execute_python` | `execute_python()` | default | Execute the generated Python code. |
| `execute_sql` | `execute_sql()` | default | Execute the generated SQL query. |

## Edges

| From | To | Condition | Type |
|------|----|-----------|------|
| `START` | `analyze_task` | `—` | direct |
| `analyze_task` | `generate_code` | `—` | direct |
| `execute_python` | `END` | `failed` | conditional |
| `execute_python` | `generate_code` | `retry` | conditional |
| `generate_code` | `execute_python` | `python_only` | conditional |
| `generate_code` | `execute_sql` | `sql` | conditional |
| `execute_sql` | `END` | `—` | direct |
