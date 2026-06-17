"""Generic local camera driver with preset URL templates.

Supports RTSP and HTTP-MJPEG cameras from Reolink, Tapo, Hiseeu,
EOOEIES, and other off-market brands that expose a local stream.
"""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState

logger = logging.getLogger(__name__)

CAMERA_PRESETS: Dict[str, Dict[str, Any]] = {
    "generic_onvif": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/stream1",
        "snapshot_template": "http://{username}:{password}@{ip}/onvif/snapshot",
    },
    "reolink": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/h264Preview_01_main",
        "snapshot_template": (
            "http://{ip}/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=xyz"
            "&user={username}&password={password}"
        ),
    },
    "tapo": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/stream1",
        "snapshot_template": "http://{username}:{password}@{ip}/onvif/snapshot",
    },
    "hiseeu": {
        "protocol": "rtsp",
        "stream_template": (
            "rtsp://{username}:{password}@{ip}:554/"
            "user={username}_password={password}_channel=1_stream=0.sdp"
        ),
        "snapshot_template": "http://{username}:{password}@{ip}/snapshot.jpg",
    },
    "eoeeies": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/live",
        "snapshot_template": "http://{username}:{password}@{ip}/snapshot",
    },
    "mjpeg": {
        "protocol": "mjpeg",
        "stream_template": "http://{username}:{password}@{ip}/video",
        "snapshot_template": "http://{username}:{password}@{ip}/snapshot",
    },
}


class GenericCameraDriver(BaseDriver):
    """Driver for generic local IP cameras using preset URL templates."""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._ip = device_config.get(
            "ip", device_config.get("ip_address", "192.168.1.100")
        )
        self._username = device_config.get("username", "")
        self._password = device_config.get("password", "")
        self._preset = device_config.get("model", "generic_onvif")
        self._stream_url = device_config.get("stream_url")
        self._snapshot_url = device_config.get("snapshot_url")
        self._power = device_config.get("power", True)

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        return self._session

    def _format_url(self, template: str) -> str:
        return template.format(
            ip=self._ip,
            username=self._username,
            password=self._password,
        )

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Verify camera is reachable by fetching a snapshot."""
        self._username = credentials.get("username", self._username)
        self._password = credentials.get("password", self._password)
        preset = CAMERA_PRESETS.get(self._preset)
        if not preset:
            logger.warning("Unknown camera preset '%s' for %s", self._preset, self.device_id)
            return False
        snapshot_url = self._snapshot_url or self._format_url(preset["snapshot_template"])
        try:
            session = self._ensure_session()
            async with session.get(
                snapshot_url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                self._connected = resp.status == 200
                return self._connected
        except Exception as exc:
            logger.warning(
                "GenericCamera authenticate failed for %s: %s", self.device_id, exc
            )
            self._connected = False
            return False

    async def get_state(self) -> DeviceState:
        """Return normalized state including stream and snapshot URLs."""
        preset = CAMERA_PRESETS.get(self._preset, {})
        stream_url = self._stream_url
        snapshot_url = self._snapshot_url
        if preset:
            stream_url = stream_url or self._format_url(preset["stream_template"])
            snapshot_url = snapshot_url or self._format_url(preset["snapshot_template"])
        return DeviceState(
            device_id=self.device_id,
            manufacturer=self.manufacturer,
            model=self._preset,
            device_type="camera",
            online=self._connected,
            state={
                "power": self._power,
                "stream_url": stream_url,
                "snapshot_url": snapshot_url,
                "ip_address": self._ip,
                "protocol": preset.get("protocol"),
            },
            last_updated=time.time(),
        )

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Apply privacy (power) toggles."""
        power = payload.get("power")
        if power is not None:
            self._power = bool(power)
        return True

    async def capture_snapshot(self) -> Optional[bytes]:
        """Fetch a JPEG snapshot from the camera."""
        preset = CAMERA_PRESETS.get(self._preset)
        if not preset:
            return None
        snapshot_url = self._snapshot_url or self._format_url(preset["snapshot_template"])
        try:
            session = self._ensure_session()
            async with session.get(
                snapshot_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                logger.warning(
                    "Snapshot for %s returned HTTP %s", self.device_id, resp.status
                )
                return None
        except Exception as exc:
            logger.warning("Snapshot failed for %s: %s", self.device_id, exc)
            return None

    async def get_stream_url(self) -> Optional[str]:
        """Return the camera's RTSP/MJPEG stream URL."""
        if self._stream_url:
            return self._stream_url
        preset = CAMERA_PRESETS.get(self._preset)
        if not preset:
            return None
        return self._format_url(preset["stream_template"])

    async def disconnect(self) -> None:
        """Close the aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
        self._connected = False


def register(plugin_loader) -> None:
    """Register every preset as a model-specific driver."""
    for preset in CAMERA_PRESETS:
        plugin_loader.register_model_driver(preset, GenericCameraDriver)
