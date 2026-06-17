import time
import uuid
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient

from core.base_driver import BaseDriver, DeviceState
from main import app


class FakeCameraDriver(BaseDriver):
    """Minimal camera driver that returns a known snapshot."""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._connected = True
        self._power = True

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        return True

    async def get_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer=self.manufacturer,
            model=self.model,
            device_type="camera",
            online=self._connected,
            state={"power": self._power},
            last_updated=time.time(),
        )

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        power = payload.get("power")
        if power is not None:
            self._power = bool(power)
        return True

    async def capture_snapshot(self) -> bytes:
        return b"FAKE_JPEG_BYTES"

    async def disconnect(self) -> None:
        self._connected = False


@pytest.mark.asyncio
async def test_camera_snapshot_uses_driver(db_session):
    device_id = f"fake-cam-{uuid.uuid4().hex[:8]}"

    def fake_get_driver_class(model: str):
        if model == "fake-cam":
            return FakeCameraDriver
        return None

    async with app.router.lifespan_context(app):
        app.state.plugin_loader.get_driver_class = fake_get_driver_class

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            add_response = await client.post(
                "/api/devices/manual",
                json={
                    "device_id": device_id,
                    "manufacturer": "fake",
                    "model": "fake-cam",
                    "device_type": "camera",
                    "name": "Fake Camera",
                },
            )
            assert add_response.status_code == 200

            snapshot_response = await client.get(f"/api/cameras/{device_id}/snapshot")
            assert snapshot_response.status_code == 200
            assert snapshot_response.headers["content-type"] == "image/jpeg"
            assert snapshot_response.content == b"FAKE_JPEG_BYTES"
