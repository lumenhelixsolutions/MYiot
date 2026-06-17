"""Philips Hue bridge plugin — REST API communication."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartLightPayload

logger = logging.getLogger(__name__)


def _brightness_to_hue(percent: int) -> int:
    """Translate 0-100 brightness percentage to Hue 0-254 scale."""
    return int(max(0, min(254, round(percent * 254 / 100))))


def _hue_to_brightness(bri: int) -> int:
    """Translate Hue 0-254 brightness to 0-100 percentage."""
    return int(max(0, min(100, round(bri * 100 / 254))))


def _color_to_xy(color_value) -> Optional[list]:
    """Convert CSS hex or RGB tuple to Hue xy color coordinates."""
    try:
        if isinstance(color_value, str) and color_value.startswith("#"):
            hex_color = color_value.lstrip("#")
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        elif isinstance(color_value, (list, tuple)) and len(color_value) == 3:
            rgb = color_value
        else:
            return None
        # Simplified RGB to xy conversion
        r, g, b = [x / 255.0 for x in rgb]
        # Apply gamma correction
        r = pow((r + 0.055) / 1.055, 2.4) if r > 0.04045 else r / 12.92
        g = pow((g + 0.055) / 1.055, 2.4) if g > 0.04045 else g / 12.92
        b = pow((b + 0.055) / 1.055, 2.4) if b > 0.04045 else b / 12.92
        X = r * 0.664511 + g * 0.154324 + b * 0.162028
        Y = r * 0.283881 + g * 0.668433 + b * 0.047685
        Z = r * 0.000088 + g * 0.072310 + b * 0.986039
        total = X + Y + Z
        if total == 0:
            return [0.0, 0.0]
        return [round(X / total, 4), round(Y / total, 4)]
    except Exception:
        return None


class PhilipsHuePlugin(BaseDriver):
    """Philips Hue Bridge plugin driver.

    Communicates via the Hue REST API to control smart lights.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._ip = device_config.get("ip", "192.168.1.2")
        self._username = device_config.get("username", "")
        self._base_url = f"http://{self._ip}/api/{self._username}"

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with the Hue bridge using username token."""
        self._username = credentials.get("username", self._username)
        self._base_url = f"http://{self._ip}/api/{self._username}"
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            async with self._session.get(f"{self._base_url}/config") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._connected = True
                    logger.info("PhilipsHuePlugin: authenticated to bridge %s", self._ip)
                    return True
                logger.warning("PhilipsHuePlugin: auth failed, status %s", resp.status)
                return False
        except Exception as exc:
            logger.error("PhilipsHuePlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET /api/{username}/lights and parse response into DeviceState."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        try:
            url = f"{self._base_url}/lights/{self.device_id}"
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = data.get("state", {})
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="philips_hue",
                        model=data.get("modelid", "hue_light"),
                        device_type="light",
                        online=True,
                        state={
                            "power": state.get("on", False),
                            "brightness": _hue_to_brightness(state.get("bri", 0)),
                            "reachable": state.get("reachable", False),
                            "color": state.get("xy"),
                        },
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("PhilipsHuePlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("PhilipsHuePlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """PUT /api/{username}/lights/{id}/state with translated payload."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        hue_payload: Dict[str, Any] = {}
        if "power" in payload and payload["power"] is not None:
            hue_payload["on"] = bool(payload["power"])
        if "brightness" in payload and payload["brightness"] is not None:
            hue_payload["bri"] = _brightness_to_hue(int(payload["brightness"]))
        if "color" in payload and payload["color"] is not None:
            xy = _color_to_xy(payload["color"])
            if xy:
                hue_payload["xy"] = xy
        try:
            url = f"{self._base_url}/lights/{self.device_id}/state"
            async with self._session.put(url, json=hue_payload) as resp:
                success = 200 <= resp.status < 300
                logger.info(
                    "PhilipsHuePlugin: set_state -> %s (status=%s)",
                    hue_payload,
                    resp.status,
                )
                return success
        except Exception as exc:
            logger.error("PhilipsHuePlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("PhilipsHuePlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        """Return an offline DeviceState."""
        return DeviceState(
            device_id=self.device_id,
            manufacturer="philips_hue",
            model=self.model,
            device_type="light",
            online=False,
            state={},
            last_updated=time.time(),
        )
