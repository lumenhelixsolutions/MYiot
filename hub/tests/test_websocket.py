import pytest
from fastapi.testclient import TestClient

from core.plugin_loader import PluginLoader
from core.state_registry import StateRegistry
from main import app
from models.database import DeviceConfig, get_async_session_factory
from services.device_manager import DeviceManager


@pytest.mark.asyncio
async def test_websocket_command_via_device_manager(db_session):
    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()
    manager = DeviceManager(registry, loader)

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

    await manager.load_devices()

    app.state.registry = registry
    app.state.device_manager = manager

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({
                "action": "command",
                "device_id": "sim-plug-01",
                "payload": {"power": False},
            })

            messages = [ws.receive_json(), ws.receive_json()]
            command_results = [m for m in messages if m["type"] == "command_result"]
            state_changes = [m for m in messages if m["type"] == "state_change"]

            assert len(command_results) == 1
            assert command_results[0]["device_id"] == "sim-plug-01"
            assert command_results[0]["success"] is True

            assert len(state_changes) == 1
            assert state_changes[0]["device_id"] == "sim-plug-01"
            assert state_changes[0]["state"]["state"]["power"] is False
