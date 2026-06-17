"""Honeywell thermostat plugin — REST API with OAuth2."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import ThermostatPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://api.honeywell.com/v2"


def _translate_from_honeywell(device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Honeywell device response into standardized state."""
    state = {}
    changeable = device.get("changeableValues", {})
    state["mode"] = changeable.get("mode", "off").lower()
    heat_sp = changeable.get("heatSetpoint", {}).get("value")
    cool_sp = changeable.get("coolSetpoint", {}).get("value")
    state["target_temp_heat"] = heat_sp
    state["target_temp_cool"] = cool_sp
    state["current_temp"] = device.get("indoorTemperature")
    state["humidity"] = device.get("displayedOutdoorHumidity")
    state["fan_mode"] = device.get("fanMode", "auto")
    state["allowed_modes"] = device.get("allowedModes", [])
    return state


def _translate_to_honeywell(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard ThermostatPayload to Honeywell format."""
    hw: Dict[str, Any] = {}
    mode = payload.get("mode")
    if mode is not None:
        hw["mode"] = mode.upper()
    target_temp = payload.get("target_temp")
    if target_temp is not None:
        hw["heatSetpoint"] = target_temp
        hw["coolSetpoint"] = target_temp
    return hw


class HoneywellPlugin(BaseDriver):
    """Honeywell thermostat plugin driver.

    Uses the Honeywell Lyric API with OAuth2 authentication.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._access_token = device_config.get("access_token", "")
        self._location_id = device_config.get("location_id", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Validate OAuth2 access token."""
        self._access_token = credentials.get("access_token", self._access_token)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with self._session.get(
                f"{BASE_URL}/devices/thermostats",
                headers=headers,
            ) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("HoneywellPlugin: OAuth token validated")
                else:
                    logger.warning("HoneywellPlugin: auth failed: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("HoneywellPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET /devices/thermostats/{deviceId} for specific device."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with self._session.get(
                f"{BASE_URL}/devices/thermostats/{self.device_id}",
                headers=headers,
                params={"locationId": self._location_id},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = _translate_from_honeywell(data)
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="honeywell",
                        model=data.get("model", "honeywell_thermostat"),
                        device_type="thermostat",
                        online=True,
                        state=state,
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("HoneywellPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("HoneywellPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST device changes to thermostat endpoint."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        hw_payload = _translate_to_honeywell(payload)
        if not hw_payload:
            logger.warning("HoneywellPlugin: empty translated payload")
            return False
        try:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with self._session.post(
                f"{BASE_URL}/devices/thermostats/{self.device_id}",
                headers=headers,
                params={"locationId": self._location_id},
                json=hw_payload,
            ) as resp:
                success = 200 <= resp.status < 300
                logger.info(
                    "HoneywellPlugin: set_state -> %s (success=%s)",
                    hw_payload,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("HoneywellPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("HoneywellPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="honeywell",
            model=self.model,
            device_type="thermostat",
            online=False,
            state={},
            last_updated=time.time(),
        )
