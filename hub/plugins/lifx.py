"""LIFX smart bulb plugin — REST API via LIFX Cloud."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartLightPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lifx.com/v1"


def _translate_to_lifx(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard SmartLightPayload to LIFX API format.

    LIFX uses: power (on/off), brightness (0.0-1.0), color (CSS string).
    """
    lifx_payload: Dict[str, Any] = {}
    power = payload.get("power")
    if power is not None:
        lifx_payload["power"] = "on" if power else "off"
    brightness = payload.get("brightness")
    if brightness is not None:
        # Convert 0-100 to 0.0-1.0
        lifx_payload["brightness"] = max(0.0, min(1.0, brightness / 100.0))
    color = payload.get("color")
    if color is not None:
        if isinstance(color, (tuple, list)) and len(color) == 3:
            lifx_payload["color"] = f"rgb:{color[0]},{color[1]},{color[2]}"
        else:
            lifx_payload["color"] = str(color)
    return lifx_payload


def _translate_from_lifx(data: Dict[str, Any]) -> Dict[str, Any]:
    """Translate LIFX API response to standardized state."""
    state = {}
    power = data.get("power", "off")
    state["power"] = power in ("on", True, 1)
    brightness = data.get("brightness")
    if brightness is not None:
        state["brightness"] = int(max(0, min(100, round(brightness * 100))))
    else:
        state["brightness"] = 0
    color = data.get("color")
    if color:
        state["color"] = color.get("name", "unknown")
    state["connected"] = data.get("connected", False)
    state["label"] = data.get("label", "")
    return state


class LifxPlugin(BaseDriver):
    """LIFX smart bulb plugin driver.

    Uses the LIFX Cloud REST API with Bearer token authentication.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._token = device_config.get("token", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Validate Bearer token with a test request."""
        self._token = credentials.get("token", self._token)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            headers = {"Authorization": f"Bearer {self._token}"}
            async with self._session.get(f"{BASE_URL}/lights/all", headers=headers) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("LifxPlugin: Bearer token validated")
                else:
                    logger.warning("LifxPlugin: auth failed: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("LifxPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET /lights/{selector} for a specific device."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._token}"}
        selector = f"id:{self.device_id}"
        try:
            async with self._session.get(
                f"{BASE_URL}/lights/{selector}", headers=headers
            ) as resp:
                if resp.status == 200:
                    data_list = await resp.json()
                    if data_list:
                        data = data_list[0]
                        state = _translate_from_lifx(data)
                        return DeviceState(
                            device_id=self.device_id,
                            manufacturer="lifx",
                            model=data.get("product", {}).get("name", "lifx_bulb"),
                            device_type="light",
                            online=state.get("connected", False),
                            state=state,
                            last_updated=time.time(),
                        )
                logger.warning("LifxPlugin: get_state status %s", resp.status)
                return self._offline_state()
        except Exception as exc:
            logger.error("LifxPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """PUT /lights/{selector}/state with translated payload."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        lifx_payload = _translate_to_lifx(payload)
        if not lifx_payload:
            logger.warning("LifxPlugin: empty translated payload")
            return False
        headers = {"Authorization": f"Bearer {self._token}"}
        selector = f"id:{self.device_id}"
        try:
            async with self._session.put(
                f"{BASE_URL}/lights/{selector}/state",
                headers=headers,
                json=lifx_payload,
            ) as resp:
                success = 200 <= resp.status < 300
                logger.info(
                    "LifxPlugin: set_state -> %s (success=%s)",
                    lifx_payload,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("LifxPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("LifxPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="lifx",
            model=self.model,
            device_type="light",
            online=False,
            state={},
            last_updated=time.time(),
        )
