import json
from typing import Optional

from app.core.redis_client import redis_client


class StateManager:
    ## Research State Management
    async def save_research_state(self, task_id: str, state: dict, ttl: int = 3600):
        await redis_client.set_json(f"research:{task_id}", state, ex=ttl)

    async def get_research_state(self, task_id: str) -> Optional[dict]:
        return await redis_client.get_json(f"research:{task_id}")

    async def delete_research_state(self, task_id: str):
        r = await redis_client.connect()
        await r.delete(f"research:{task_id}")

    ## Orchestrator State Management
    async def save_orchestrator_state(self, task_id: str, state: dict, ttl: int = 3600):
        await redis_client.set_json(f"orchestrator:{task_id}", state, ex=ttl)


state_manager = StateManager()
