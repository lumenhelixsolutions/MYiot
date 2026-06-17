import os

import pytest
import pytest_asyncio
from sqlalchemy import delete

# Use an in-memory database for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SEED_DEMO_DEVICES", "false")

from main import app
from models.database import get_async_session_factory, init_db


@pytest_asyncio.fixture
async def db_session():
    await init_db()
    factory = get_async_session_factory()
    async with factory() as session:
        # Ensure each test starts with empty tables.
        from models.database import DeviceConfig, EventLog
        await session.execute(delete(DeviceConfig))
        await session.execute(delete(EventLog))
        await session.commit()
        yield session


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    return TestClient(app)
