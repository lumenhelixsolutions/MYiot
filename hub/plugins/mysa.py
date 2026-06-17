"""Mysa thermostat plugin — REST API with Bearer token."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import ThermostatPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://api.mysa.energy/v1"


def _translate_from_mysa(device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Mysa device response into standardized state."""
    state = {}
    state["mode"] = device.get("mode", "off").lower()
    state["target_temp"] = device.get("set_point")
    state["current_temp"] = device.get("room_temperature")
    state["humidity"] = device.get("humidity")
    state["power_usage"] = device.get("power_usage_watts")
    state["heating"] = device.get("is_heating", False)
    state["online"] = device.get("is_online", False)
    state["eco_mode"] = device.get("eco_mode", False)
    return state


def _translate_to_mysa(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard ThermostatPayload to Mysa format."""
    mysa: Dict[str, Any] = {}
    mode = payload.get("mode")
    if mode is not None:
        mysa["mode"] = mode.upper()
    target_temp = payload.get("target_temp")
    if target_temp is not None:
        mysa["set_point"] = target_temp
    return mysa


class MysaPlugin(BaseDriver):
    """Mysa thermostat plugin driver.

    Uses the Mysa REST API with Bearer token authentication.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._bearer_token = device_config.get("bearer_token", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Validate Bearer token."""
        self._bearer_token = credentials.get("bearer_token", self._bearer_token)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            headers = {"Authorization": f"Bearer {self._bearer_token}"}
            async with self._session.get(
                f"{BASE_URL}/devices",
                headers=headers,
            ) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("MysaPlugin: Bearer token validated")
                else:
                    logger.warning("MysaPlugin: auth failed: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("MysaPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET device status for a specific thermostat."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._bearer_token}"}
        try:
            async with self._session.get(
                f"{BASE_URL}/devices/{self.device_id}",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = _translate_from_mysa(data)
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="mysa",
                        model=data.get("model", "mysa_thermostat"),
                        device_type="thermostat",
                        online=state.get("online", False),
                        state=state,
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("MysaPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("MysaPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST temperature/mode changes."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        mysa_payload = _translate_to_mysa(payload)
        if not mysa_payload:
            logger.warning("MysaPlugin: empty translated payload")
            return False
        try:
            headers = {"Authorization": f"Bearer {self._bearer_token}"}
            async with self._session.post(
                f"{BASE_URL}/devices/{self.device_id}/settings",
                headers=headers,
                json=mysa_payload,
            ) as resp:
                success = 200 <= resp.status < 300
                logger.info(
                    "MysaPlugin: set_state -> %s (success=%s)",
                    mysa_payload,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("MysaPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("MysaPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="mysa",
            model=self.model,
            device_type="thermostat",
            online=False,
            state={},
            last_updated=time.time(),
        )
