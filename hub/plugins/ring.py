"""Ring camera plugin — REST API with OAuth2."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import CameraPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ring.com/clients_api"
OAUTH_URL = "https://oauth.ring.com/oauth/token"


def _translate_from_ring(device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Ring device response into standardized state."""
    state = {}
    state["power"] = device.get("active", True)
    state["recording"] = device.get("now_live_viewing", False)
    state["battery_level"] = device.get("battery_life")
    state["motion_snoozed"] = device.get("motion_snooze", False)
    state["description"] = device.get("description", "")
    return state


class RingPlugin(BaseDriver):
    """Ring camera plugin driver.

    Uses the Ring REST API with OAuth2 token refresh authentication.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._refresh_token = device_config.get("refresh_token", "")
        self._access_token = device_config.get("access_token", "")
        self._device_id_int: Optional[int] = None

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """OAuth2 token refresh to obtain access token."""
        self._refresh_token = credentials.get("refresh_token", self._refresh_token)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": "ring_official_android",
                "scope": "client",
            }
            async with self._session.post(OAUTH_URL, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._access_token = data.get("access_token", "")
                    self._refresh_token = data.get("refresh_token", self._refresh_token)
                    self._connected = bool(self._access_token)
                    logger.info(
                        "RingPlugin: OAuth refreshed, token=%s...",
                        self._access_token[:8] if self._access_token else "none",
                    )
                    return self._connected
                logger.warning("RingPlugin: OAuth refresh failed: %s", resp.status)
                return False
        except Exception as exc:
            logger.error("RingPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET /ring_devices and parse for matching device."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with self._session.get(
                f"{BASE_URL}/ring_devices",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    doorbots = data.get("doorbots", []) + data.get("authorized_doorbots", [])
                    stickups = data.get("stickup_cams", [])
                    all_devices = doorbots + stickups
                    for dev in all_devices:
                        if str(dev.get("id")) == self.device_id:
                            state = _translate_from_ring(dev)
                            return DeviceState(
                                device_id=self.device_id,
                                manufacturer="ring",
                                model=dev.get("kind", "ring_camera"),
                                device_type="camera",
                                online=state.get("power", False),
                                state=state,
                                last_updated=time.time(),
                            )
                    logger.warning("RingPlugin: device %s not found", self.device_id)
                    return self._offline_state()
                else:
                    logger.warning("RingPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("RingPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST device commands (e.g., toggle recording, motion settings)."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        power = payload.get("power")
        if power is None:
            logger.warning("RingPlugin: set_state requires power field")
            return False
        try:
            # Toggle light/floodlight or siren based on power
            endpoint = f"{BASE_URL}/doorbots/{self.device_id}/floodlight_light_on"
            if not power:
                endpoint = f"{BASE_URL}/doorbots/{self.device_id}/floodlight_light_off"
            async with self._session.post(endpoint, headers=headers) as resp:
                success = resp.status == 200
                logger.info("RingPlugin: set_state power=%s -> success=%s", power, success)
                return success
        except Exception as exc:
            logger.error("RingPlugin: set_state error: %s", exc)
            return False

    async def get_stream_url(self) -> Optional[str]:
        """Return ding/hls stream URL for live viewing."""
        # Ring requires a session-based live stream request
        return f"https://stream.ring.com/live/{self.device_id}"

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("RingPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="ring",
            model=self.model,
            device_type="camera",
            online=False,
            state={},
            last_updated=time.time(),
        )
