"""End-to-end acceptance test for a pluggable local driver.

Proves that a runtime/local driver class can be registered by model and
commanded through the public ``/api/devices/{id}/command`` endpoint, with the
device manager routing the command to the correct driver instance.
"""

import time
import uuid
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient

from core.base_driver import BaseDriver, DeviceState
from main import app


class FakeLocalDriver(BaseDriver):
    """Minimal local driver used to validate end-to-end command routing."""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self.power = False
        self.brightness = 0

    async def connect(self) -> None:
        """Mark the driver as connected."""
        self._connected = True

    async def disconnect(self) -> None:
        """Mark the driver as disconnected."""
        self._connected = False

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Local fake driver needs no credentials; just connect."""
        await self.connect()
        return True

    async def get_state(self) -> DeviceState:
        """Return the current local state as a standardized DeviceState."""
        return DeviceState(
            device_id=self.device_id,
            manufacturer=self.manufacturer,
            model=self.model,
            device_type=self.device_type,
            online=self._connected,
            state={"power": self.power, "brightness": self.brightness},
            last_updated=time.time(),
        )

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Apply matching keys from the command payload to local attributes."""
        for key, value in payload.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return True


@pytest.mark.asyncio
async def test_fake_local_driver_end_to_end(db_session):
    """A fake local driver can be loaded, registered, and commanded via HTTP."""
    device_id = f"fake-local-light-{uuid.uuid4().hex[:8]}"

    def fake_get_driver_class(model: str):
        if model == "fake-local-light":
            return FakeLocalDriver
        return None

    async with app.router.lifespan_context(app):
        # Patch the running plugin loader so our fake model resolves to the
        # fake driver class.
        app.state.plugin_loader.get_driver_class = fake_get_driver_class

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            add_response = await client.post(
                "/api/devices/manual",
                json={
                    "device_id": device_id,
                    "manufacturer": "fake",
                    "model": "fake-local-light",
                    "device_type": "light",
                    "name": "Fake Local Light",
                },
            )
            assert add_response.status_code == 200
            assert add_response.json()["success"] is True

            cmd_response = await client.post(
                f"/api/devices/{device_id}/command",
                json={"payload": {"power": True, "brightness": 75}},
            )
            assert cmd_response.status_code == 200
            data = cmd_response.json()
            assert data["success"] is True
            assert data["device_id"] == device_id

            # The manager should have routed the command to our FakeLocalDriver.
            driver = app.state.device_manager._drivers.get(device_id)
            assert driver is not None
            assert isinstance(driver, FakeLocalDriver)
            assert driver._connected is True
            assert driver.power is True
            assert driver.brightness == 75

            # The registry should reflect the updated state returned by the driver.
            state = await app.state.registry.get(device_id)
            assert state is not None
            assert state.state["power"] is True
            assert state.state["brightness"] == 75
