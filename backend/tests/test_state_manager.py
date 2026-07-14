from unittest.mock import AsyncMock, patch

import pytest

from app.core.state_manager import state_manager

FAKE_TASK_ID = "task-123"
FAKE_STATE = {"key": "value", "number": 42}


class TestStateManager:
    @pytest.mark.asyncio
    async def test_save_research_state(self):
        with patch("app.core.state_manager.redis_client") as mock_redis:
            mock_redis.set_json = AsyncMock()
            await state_manager.save_research_state(FAKE_TASK_ID, FAKE_STATE)

        mock_redis.set_json.assert_awaited_once_with(
            f"research:{FAKE_TASK_ID}", FAKE_STATE, ex=3600,
        )

    @pytest.mark.asyncio
    async def test_save_research_state_custom_ttl(self):
        with patch("app.core.state_manager.redis_client") as mock_redis:
            mock_redis.set_json = AsyncMock()
            await state_manager.save_research_state(FAKE_TASK_ID, FAKE_STATE, ttl=600)

        mock_redis.set_json.assert_awaited_once_with(
            f"research:{FAKE_TASK_ID}", FAKE_STATE, ex=600,
        )

    @pytest.mark.asyncio
    async def test_get_research_state_exists(self):
        with patch("app.core.state_manager.redis_client") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=FAKE_STATE)
            result = await state_manager.get_research_state(FAKE_TASK_ID)

        assert result == FAKE_STATE
        mock_redis.get_json.assert_awaited_once_with(f"research:{FAKE_TASK_ID}")

    @pytest.mark.asyncio
    async def test_get_research_state_returns_none(self):
        with patch("app.core.state_manager.redis_client") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=None)
            result = await state_manager.get_research_state(FAKE_TASK_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_research_state(self):
        with patch("app.core.state_manager.redis_client") as mock_redis:
            mock_redis_instance = AsyncMock()
            mock_redis.connect = AsyncMock(return_value=mock_redis_instance)
            mock_redis.set_json = AsyncMock()

            await state_manager.delete_research_state(FAKE_TASK_ID)

        mock_redis.connect.assert_awaited_once()
        mock_redis_instance.delete.assert_awaited_once_with(
            f"research:{FAKE_TASK_ID}",
        )

    @pytest.mark.asyncio
    async def test_save_orchestrator_state(self):
        with patch("app.core.state_manager.redis_client") as mock_redis:
            mock_redis.set_json = AsyncMock()
            await state_manager.save_orchestrator_state(FAKE_TASK_ID, FAKE_STATE)

        mock_redis.set_json.assert_awaited_once_with(
            f"orchestrator:{FAKE_TASK_ID}", FAKE_STATE, ex=3600,
        )

    @pytest.mark.asyncio
    async def test_save_orchestrator_state_custom_ttl(self):
        with patch("app.core.state_manager.redis_client") as mock_redis:
            mock_redis.set_json = AsyncMock()
            await state_manager.save_orchestrator_state(
                FAKE_TASK_ID, FAKE_STATE, ttl=120,
            )

        mock_redis.set_json.assert_awaited_once_with(
            f"orchestrator:{FAKE_TASK_ID}", FAKE_STATE, ex=120,
        )
