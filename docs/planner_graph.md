# Planner Agent

**Source**: `app/core/agents/planner.py`

## State

| Field | Type |
|-------|------|
| `task_description` | `str` |
| `plan` | `Optional[Plan]` |
| `error` | `Optional[str]` |
| `llm_response` | `Optional[str]` |

## Flow Diagram

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;

    parse("📋 parse")
    generate("🤖 generate")
    validate("✓ validate")

    __start__(["Start"]):::first --> validate;
    generate --> parse;
    parse -. &nbsp;complete&nbsp; .-> __end__(["End"]):::last;
    validate -. &nbsp;error&nbsp; .-> __end__(["End"]):::last;
    validate -. &nbsp;continue&nbsp; .-> generate;

    class parse parseNode;
    class generate llmNode;
    class validate validationNode;
    classDef first fill-opacity:0;
    classDef last fill:#bfb6fc;
    classDef validationNode fill:#4caf50,stroke:#333,stroke-width:2px,color:#fff;
    classDef llmNode fill:#2196f3,stroke:#333,stroke-width:2px,color:#fff;
    classDef parseNode fill:#ff9800,stroke:#333,stroke-width:2px,color:#fff;
```

## Nodes

| Node | Function | Type | Description |
|------|----------|------|-------------|
| `validate` | `validate_task()` | validation | Validate that the task description is not empty. |
| `generate` | `generate_plan()` | llm | Call the LLM to generate a plan. |
| `parse` | `parse_plan()` | parse | Parse and validate the LLM response into a Plan. |

## Edges

| From | To | Condition | Type |
|------|----|-----------|------|
| `START` | `validate` | `—` | direct |
| `generate` | `parse` | `—` | direct |
| `parse` | `END` | `complete` | conditional |
| `validate` | `END` | `error` | conditional |
| `validate` | `generate` | `continue` | conditional |
