"""Wyze plugin — REST API via Wyze SDK pattern."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import (
    SmartLightPayload,
    SmartPlugPayload,
    CameraPayload,
    ThermostatPayload,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.wyzecam.com"


def _translate_to_wyze(device_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard payload to Wyze API format."""
    wyze_payload: Dict[str, Any] = {}
    if device_type == "light" or device_type == "plug":
        power = payload.get("power")
        if power is not None:
            wyze_payload["power"] = 1 if power else 0
        brightness = payload.get("brightness")
        if brightness is not None:
            wyze_payload["brightness"] = max(0, min(100, int(brightness)))
        color = payload.get("color")
        if color is not None:
            wyze_payload["color"] = str(color)
    elif device_type == "thermostat":
        mode = payload.get("mode")
        if mode is not None:
            wyze_payload["mode"] = mode
        target_temp = payload.get("target_temp")
        if target_temp is not None:
            wyze_payload["cool_set_point"] = target_temp
            wyze_payload["heat_set_point"] = target_temp
    elif device_type == "camera":
        power = payload.get("power")
        if power is not None:
            wyze_payload["switch_state"] = 1 if power else 0
    return wyze_payload


def _translate_from_wyze(device_type: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Wyze device raw state into standardized state."""
    state: Dict[str, Any] = {}
    props = raw.get("property_list", raw.get("device_params", {}))
    if device_type in ("light", "plug"):
        pwr = props.get("power", props.get("P3", 0))
        state["power"] = pwr in (1, "1", True, "on")
        bri = props.get("brightness", props.get("P1501", 0))
        state["brightness"] = int(bri) if bri else 0
    elif device_type == "thermostat":
        state["mode"] = props.get("mode", props.get("P3", "off"))
        state["target_temp"] = props.get("cool_set_point", props.get("P1502"))
        state["current_temp"] = props.get("temperature", props.get("P1501"))
    elif device_type == "camera":
        pwr = props.get("switch_state", props.get("power", 0))
        state["power"] = pwr in (1, "1", True)
        state["recording"] = props.get("motion_record", False)
    state["online"] = raw.get("conn_state", 1) == 1
    return state


class WyzePlugin(BaseDriver):
    """Wyze plugin driver for lights, cameras, and plugs.

    Uses the Wyze REST API with email/password authentication.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._email = device_config.get("email", "")
        self._password = device_config.get("password", "")
        self._api_key = device_config.get("api_key", "")
        self._access_token = ""

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with email and password to get access token."""
        self._email = credentials.get("email", self._email)
        self._password = credentials.get("password", self._password)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            payload = {
                "email": self._email,
                "password": self._password,
                "sc": "wyze_developer_api",
                "sv": "1",
                "app_ver": "com.hualai.WyzeCam___2.18.44",
            }
            async with self._session.post(
                f"{BASE_URL}/app/user/login", json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._access_token = data.get("access_token", "")
                    self._connected = bool(self._access_token)
                    logger.info(
                        "WyzePlugin: authenticated, token=%s...",
                        self._access_token[:8] if self._access_token else "none",
                    )
                    return self._connected
                logger.warning("WyzePlugin: auth failed: %s", resp.status)
                return False
        except Exception as exc:
            logger.error("WyzePlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """List devices and parse state for matching device_id."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with self._session.get(
                f"{BASE_URL}/app/v2/home_page/get_object_list",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    devices = data.get("data", {}).get("device_list", [])
                    for dev in devices:
                        if dev.get("mac") == self.device_id or dev.get("did") == self.device_id:
                            state = _translate_from_wyze(self.device_type, dev)
                            return DeviceState(
                                device_id=self.device_id,
                                manufacturer="wyze",
                                model=dev.get("product_model", "wyze_device"),
                                device_type=self.device_type,
                                online=state.get("online", False),
                                state=state,
                                last_updated=time.time(),
                            )
                    logger.warning("WyzePlugin: device %s not found", self.device_id)
                    return self._offline_state()
                else:
                    logger.warning("WyzePlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("WyzePlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Send device-specific command via Wyze API."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        wyze_payload = _translate_to_wyze(self.device_type, payload)
        if not wyze_payload:
            logger.warning("WyzePlugin: empty translated payload")
            return False
        try:
            body = {
                "did": self.device_id,
                "mac": self.device_id,
                "model": self.model,
                "pid": "P3",
                "pvalue": str(wyze_payload.get("power", 0)),
                "access_token": self._access_token,
            }
            async with self._session.post(
                f"{BASE_URL}/app/v2/device/set_property",
                json=body,
            ) as resp:
                success = resp.status == 200
                logger.info("WyzePlugin: set_state -> %s (success=%s)", wyze_payload, success)
                return success
        except Exception as exc:
            logger.error("WyzePlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("WyzePlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="wyze",
            model=self.model,
            device_type=self.device_type,
            online=False,
            state={},
            last_updated=time.time(),
        )
