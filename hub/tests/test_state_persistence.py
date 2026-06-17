import asyncio

import pytest
from sqlalchemy import select

from core.base_driver import DeviceState
from core.state_registry import StateRegistry
from models.database import DeviceConfig, get_async_session_factory
from services.state_persistence import StatePersistenceAdapter


@pytest.mark.asyncio
async def test_persistence_adapter_writes_state(db_session):
    registry = StateRegistry()
    adapter = StatePersistenceAdapter(debounce_seconds=0.1)
    adapter.attach(registry)

    state = DeviceState(
        device_id="test-plug-1",
        manufacturer="tp_link_kasa",
        model="KP125",
        device_type="plug",
        online=True,
        state={"power": True},
        last_updated=1234567890.0,
    )
    await registry.update("test-plug-1", state)
    await adapter.flush()

    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(DeviceConfig).where(DeviceConfig.device_id == "test-plug-1")
        )
        cfg = result.scalar_one_or_none()
        assert cfg is not None
        assert cfg.last_state["state"]["power"] is True

    await adapter.detach()
