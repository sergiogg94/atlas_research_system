# Orchestrator Agent

**Source**: `app/core/agents/orchestrator.py`

## State

| Field | Type |
|-------|------|
| `task_description` | `str` |
| `objective` | `str` |
| `plan` | `Optional[dict]` |
| `plan_steps` | `Optional[list]` |
| `research_findings` | `Optional[list]` |
| `data_results` | `Optional[list]` |
| `report` | `Optional[str]` |
| `error` | `Optional[str]` |
| `current_agent` | `str` |
| `step_index` | `int` |
| `total_steps` | `int` |
| `max_steps` | `int` |
| `checkpoint_idx` | `Optional[str]` |
| `consecutive_failures` | `int` |
| `last_failure_agent` | `Optional[str]` |

## Flow Diagram

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;

    run_synthesis("⚙ run_synthesis")
    run_research("🔧 run_research")
    run_planner("⚙ run_planner")
    re_plan("⚙ re_plan")
    check_max_steps("✓ check_max_steps")
    check_degradation("✓ check_degradation")
    run_data("⚙ run_data")

    __start__(["Start"]):::first --> run_planner;
    check_degradation -. &nbsp;end&nbsp; .-> __end__(["End"]):::last;
    check_degradation -. &nbsp;&nbsp; .-> run_data;
    check_degradation -. &nbsp;&nbsp; .-> run_planner;
    check_degradation -. &nbsp;&nbsp; .-> run_research;
    check_degradation -. &nbsp;&nbsp; .-> run_synthesis;
    check_max_steps -. &nbsp;end&nbsp; .-> __end__(["End"]):::last;
    check_max_steps -. &nbsp;error&nbsp; .-> re_plan;
    check_max_steps -. &nbsp;data&nbsp; .-> run_data;
    check_max_steps -. &nbsp;research&nbsp; .-> run_research;
    check_max_steps -. &nbsp;synthesis&nbsp; .-> run_synthesis;
    re_plan --> check_degradation;
    run_data --> check_max_steps;
    run_planner --> check_max_steps;
    run_research --> check_max_steps;
    run_synthesis --> __end__(["End"]):::last;

    class run_synthesis,run_planner,re_plan,run_data defaultNode;
    class run_research toolNode;
    class check_max_steps,check_degradation validationNode;
    classDef first fill-opacity:0;
    classDef last fill:#bfb6fc;
    classDef validationNode fill:#4caf50,stroke:#333,stroke-width:2px,color:#fff;
    classDef toolNode fill:#9c27b0,stroke:#333,stroke-width:2px,color:#fff;
    classDef defaultNode fill:#607d8b,stroke:#333,stroke-width:2px,color:#fff;
```

## Nodes

| Node | Function | Type | Description |
|------|----------|------|-------------|
| `run_planner` | `run_planner()` | default | Invoke the Planner Agent to break down the task. |
| `run_research` | `run_research()` | tool | *No description* |
| `run_data` | `run_data()` | default | *No description* |
| `run_synthesis` | `run_synthesis()` | default | *No description* |
| `re_plan` | `re_plan()` | default | If an agent failed, try to re-plan with the LLM. |
| `check_max_steps` | `check_max_steps()` | validation | Prevents infinite loops by stopping at MAX_TOTAL_STEPS. |
| `check_degradation` | `check_degradation()` | validation | Detects degradation: abort after multiple consecutive failures on the same agent. |

## Edges

| From | To | Condition | Type |
|------|----|-----------|------|
| `START` | `run_planner` | `—` | direct |
| `check_degradation` | `END` | `end` | conditional |
| `check_degradation` | `run_data` | `—` | conditional |
| `check_degradation` | `run_planner` | `—` | conditional |
| `check_degradation` | `run_research` | `—` | conditional |
| `check_degradation` | `run_synthesis` | `—` | conditional |
| `check_max_steps` | `END` | `end` | conditional |
| `check_max_steps` | `re_plan` | `error` | conditional |
| `check_max_steps` | `run_data` | `data` | conditional |
| `check_max_steps` | `run_research` | `research` | conditional |
| `check_max_steps` | `run_synthesis` | `synthesis` | conditional |
| `re_plan` | `check_degradation` | `—` | direct |
| `run_data` | `check_max_steps` | `—` | direct |
| `run_planner` | `check_max_steps` | `—` | direct |
| `run_research` | `check_max_steps` | `—` | direct |
| `run_synthesis` | `END` | `—` | direct |
