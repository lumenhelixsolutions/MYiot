"""EOOEIES camera plugin — REST API with Basic Auth."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import CameraPayload

logger = logging.getLogger(__name__)


def _get_base_url(device_config: Dict[str, Any]) -> str:
    """Build base URL from device config."""
    ip = device_config.get("ip", "192.168.1.100")
    return f"http://{ip}/api/v1"


def _translate_from_eoeeies(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse EOOEIES status response into standardized state."""
    state = {}
    state["power"] = raw.get("enabled", raw.get("power", False))
    state["recording"] = raw.get("recording", False)
    state["resolution"] = raw.get("resolution", "1080p")
    state["fps"] = raw.get("fps", 30)
    state["night_mode"] = raw.get("night_mode", False)
    return state


class EoeeiesPlugin(BaseDriver):
    """EOOEIES camera plugin driver.

    Communicates via REST API with Basic Authentication.
    Provides snapshot capture and stream URL retrieval.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._ip = device_config.get("ip", "192.168.1.100")
        self._base_url = _get_base_url(device_config)
        self._username = device_config.get("username", "")
        self._password = device_config.get("password", "")

    def _auth(self) -> aiohttp.BasicAuth:
        """Return Basic Auth credentials."""
        return aiohttp.BasicAuth(self._username, self._password)

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with username and password (Basic Auth)."""
        self._username = credentials.get("username", self._username)
        self._password = credentials.get("password", self._password)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            async with self._session.get(
                f"{self._base_url}/status",
                auth=self._auth(),
            ) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("EoeeiesPlugin: authenticated to %s", self._ip)
                else:
                    logger.warning("EoeeiesPlugin: auth failed: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("EoeeiesPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET /api/v1/status and parse response."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        try:
            async with self._session.get(
                f"{self._base_url}/status",
                auth=self._auth(),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = _translate_from_eoeeies(data)
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="eoeeies",
                        model=data.get("model", "eoeeies_cam"),
                        device_type="camera",
                        online=True,
                        state=state,
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("EoeeiesPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("EoeeiesPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST /api/v1/control with translated payload."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        control_payload: Dict[str, Any] = {}
        power = payload.get("power")
        if power is not None:
            control_payload["enabled"] = bool(power)
        if not control_payload:
            logger.warning("EoeeiesPlugin: empty control payload")
            return False
        try:
            async with self._session.post(
                f"{self._base_url}/control",
                auth=self._auth(),
                json=control_payload,
            ) as resp:
                success = 200 <= resp.status < 300
                logger.info(
                    "EoeeiesPlugin: set_state -> %s (success=%s)",
                    control_payload,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("EoeeiesPlugin: set_state error: %s", exc)
            return False

    async def capture_snapshot(self) -> Optional[bytes]:
        """GET /api/v1/snapshot — return JPEG bytes."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        try:
            async with self._session.get(
                f"{self._base_url}/snapshot",
                auth=self._auth(),
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    logger.info(
                        "EoeeiesPlugin: snapshot captured, %d bytes", len(data)
                    )
                    return data
                logger.warning("EoeeiesPlugin: snapshot failed: %s", resp.status)
                return None
        except Exception as exc:
            logger.error("EoeeiesPlugin: capture_snapshot error: %s", exc)
            return None

    async def get_stream_url(self) -> Optional[str]:
        """GET /api/v1/stream — return RTSP URL."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        try:
            async with self._session.get(
                f"{self._base_url}/stream",
                auth=self._auth(),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("rtsp_url", "")
                    logger.info("EoeeiesPlugin: stream URL=%s", url)
                    return url
                logger.warning("EoeeiesPlugin: stream URL failed: %s", resp.status)
                return None
        except Exception as exc:
            logger.error("EoeeiesPlugin: get_stream_url error: %s", exc)
            return None

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("EoeeiesPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="eoeeies",
            model=self.model,
            device_type="camera",
            online=False,
            state={},
            last_updated=time.time(),
        )
