import pytest

from core.plugin_loader import PluginLoader
from core.state_registry import StateRegistry
from models.database import DeviceConfig, get_async_session_factory
from services.device_manager import DeviceManager


@pytest.mark.asyncio
async def test_simulator_command(db_session):
    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()

    factory = get_async_session_factory()
    async with factory() as session:
        cfg = DeviceConfig(
            device_id="sim-plug-01",
            manufacturer="simulator",
            device_type="plug",
            enabled=True,
        )
        session.add(cfg)
        await session.commit()

    manager = DeviceManager(registry, loader)
    await manager.load_devices()

    success = await manager.set_state("sim-plug-01", {"power": False})
    assert success is True

    state = await registry.get("sim-plug-01")
    assert state.state["power"] is False


@pytest.mark.asyncio
async def test_set_state_unknown_device(db_session):
    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()

    manager = DeviceManager(registry, loader)
    success = await manager.set_state("does-not-exist", {"power": False})
    assert success is False


@pytest.mark.asyncio
async def test_get_state_delegates(db_session):
    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()

    cfg = DeviceConfig(
        device_id="sim-plug-01",
        manufacturer="simulator",
        device_type="plug",
        enabled=True,
    )
    manager = DeviceManager(registry, loader)
    await manager.add_device(cfg)

    state = await manager.get_state("sim-plug-01")
    assert state is not None
    assert state.device_id == "sim-plug-01"
    assert state.manufacturer == "simulator"


@pytest.mark.asyncio
async def test_add_device_registers_driver(db_session):
    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()

    cfg = DeviceConfig(
        device_id="sim-plug-02",
        manufacturer="simulator",
        device_type="plug",
        enabled=True,
    )
    manager = DeviceManager(registry, loader)
    await manager.add_device(cfg)

    success = await manager.set_state("sim-plug-02", {"power": False})
    assert success is True

    state = await registry.get("sim-plug-02")
    assert state is not None
    assert state.state["power"] is False


@pytest.mark.asyncio
async def test_remove_device_disconnects_driver(db_session):
    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()

    cfg = DeviceConfig(
        device_id="sim-light-01",
        manufacturer="simulator",
        device_type="light",
        enabled=True,
    )
    manager = DeviceManager(registry, loader)
    await manager.add_device(cfg)

    success = await manager.set_state("sim-light-01", {"power": False})
    assert success is True

    await manager.remove_device("sim-light-01")

    success = await manager.set_state("sim-light-01", {"power": True})
    assert success is False
