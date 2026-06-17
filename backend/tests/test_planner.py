import pytest
from app.core.agents.planner import build_planner_graph


@pytest.mark.asyncio
async def test_planner_rejects_short_task():
    graph = build_planner_graph()
    result = await graph.ainvoke({"task_description": "Hi"})
    assert result.get("error") is not None


# TODO: Mock the LLM provider to return a predictable response and test the full planner flow
# @pytest.mark.asyncio
# async def test_planner_generates_valid_plan():
#     graph = build_planner_graph()
#     result = await graph.ainvoke(
#         {
#             "task_description": "Research the impact of AI on healthcare",
#         }
#     )
#     assert result.get("plan") is not None
#     assert len(result["plan"].steps) >= 1
#     assert result["plan"].objective
