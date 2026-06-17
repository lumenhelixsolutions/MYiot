"""Govee plugin — REST API with API key authentication."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartLightPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://developer-api.govee.com/v1"


def _translate_to_govee(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard SmartLightPayload to Govee control format."""
    govee_cmd = {"name": "turn", "value": "on"}
    power = payload.get("power")
    if power is not None:
        govee_cmd = {"name": "turn", "value": "on" if power else "off"}
    brightness = payload.get("brightness")
    if brightness is not None:
        # Govee brightness 0-100
        bri = max(0, min(100, int(brightness)))
        govee_cmd = {"name": "brightness", "value": bri}
    color = payload.get("color")
    if color is not None:
        if isinstance(color, str) and color.startswith("#"):
            hex_color = color.lstrip("#")
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            govee_cmd = {"name": "color", "value": {"r": r, "g": g, "b": b}}
        elif isinstance(color, (tuple, list)) and len(color) == 3:
            govee_cmd = {"name": "color", "value": {"r": color[0], "g": color[1], "b": color[2]}}
    return govee_cmd


def _translate_from_govee(device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Govee device response into standardized state."""
    state = {}
    props = device.get("properties", device)
    if isinstance(props, list):
        for p in props:
            if isinstance(p, dict):
                if "powerState" in p:
                    state["power"] = p["powerState"] == "on"
                if "brightness" in p:
                    state["brightness"] = int(p["brightness"])
                if "color" in p:
                    c = p["color"]
                    state["color"] = (c.get("r", 0), c.get("g", 0), c.get("b", 0))
    else:
        state["power"] = props.get("powerState", "off") == "on"
        state["brightness"] = int(props.get("brightness", 0))
        color = props.get("color", {})
        if color:
            state["color"] = (color.get("r", 0), color.get("g", 0), color.get("b", 0))
    state["online"] = device.get("isOnline", False)
    return state


class GoveePlugin(BaseDriver):
    """Govee smart light plugin driver.

    Uses the Govee Developer API with API key authentication.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._api_key = device_config.get("api_key", "")
        self._device_mac = device_config.get("device_mac", "")
        self._device_model = device_config.get("device_model", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Validate API key with a test request."""
        self._api_key = credentials.get("api_key", self._api_key)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            headers = {"Govee-API-Key": self._api_key}
            async with self._session.get(
                f"{BASE_URL}/devices",
                headers=headers,
            ) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("GoveePlugin: API key validated")
                else:
                    logger.warning("GoveePlugin: API key invalid: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("GoveePlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET /devices and parse state for matching device."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Govee-API-Key": self._api_key}
        try:
            async with self._session.get(
                f"{BASE_URL}/devices",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    devices = data.get("data", {}).get("devices", [])
                    for dev in devices:
                        if dev.get("device") == self.device_id or dev.get("mac") == self._device_mac:
                            state = _translate_from_govee(dev)
                            return DeviceState(
                                device_id=self.device_id,
                                manufacturer="govee",
                                model=dev.get("model", "govee_light"),
                                device_type="light",
                                online=state.get("online", False),
                                state=state,
                                last_updated=time.time(),
                            )
                    logger.warning("GoveePlugin: device %s not found", self.device_id)
                    return self._offline_state()
                else:
                    logger.warning("GoveePlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("GoveePlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """PUT /devices/control with translated command."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        govee_cmd = _translate_to_govee(payload)
        if not govee_cmd:
            logger.warning("GoveePlugin: empty translated payload")
            return False
        body = {
            "device": self.device_id,
            "model": self._device_model,
            "cmd": govee_cmd,
        }
        headers = {"Govee-API-Key": self._api_key, "Content-Type": "application/json"}
        try:
            async with self._session.put(
                f"{BASE_URL}/devices/control",
                headers=headers,
                json=body,
            ) as resp:
                success = resp.status == 200
                logger.info(
                    "GoveePlugin: set_state -> %s (success=%s)",
                    govee_cmd,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("GoveePlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("GoveePlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="govee",
            model=self.model,
            device_type="light",
            online=False,
            state={},
            last_updated=time.time(),
        )
