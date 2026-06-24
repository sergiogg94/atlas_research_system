import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.llm.factory import get_llm_provider
from app.core.database import engine, SessionLocal


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    """Create a fresh DB session for each test"""
    async with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
async def reset_db():
    """Reset DB state before each test"""
    # This ensures each test starts fresh
    yield


@pytest.fixture
def llm_provider():
    """Use EchoProvider for tests"""
    return get_llm_provider()
