import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.llm.factory import get_llm_provider


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def llm_provider():
    """Use EchoProvider for tests"""
    return get_llm_provider()
