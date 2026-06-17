"""Emerson Sensi thermostat plugin — REST API with OAuth2."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import ThermostatPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sensi.com"
AUTH_URL = "https://api.sensi.com/oauth2/token"


def _translate_from_sensi(device: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Sensi device response into standardized state."""
    state = {}
    state["mode"] = device.get("operating_mode", "off").lower()
    state["target_temp_heat"] = device.get("heat_setpoint")
    state["target_temp_cool"] = device.get("cool_setpoint")
    state["current_temp"] = device.get("display_temp")
    state["humidity"] = device.get("indoor_humidity")
    state["fan_mode"] = device.get("fan_mode", "auto")
    state["running"] = device.get("running", False)
    state["battery"] = device.get("battery_voltage")
    return state


def _translate_to_sensi(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard ThermostatPayload to Sensi format."""
    sensi: Dict[str, Any] = {}
    mode = payload.get("mode")
    if mode is not None:
        sensi["operating_mode"] = mode.upper()
    target_temp = payload.get("target_temp")
    if target_temp is not None:
        sensi["heat_setpoint"] = target_temp
        sensi["cool_setpoint"] = target_temp
    return sensi


class EmersonSensiPlugin(BaseDriver):
    """Emerson Sensi thermostat plugin driver.

    Uses the Sensi REST API with OAuth2 authentication.
    Similar pattern to Ecobee/Honeywell thermostats.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._client_id = device_config.get("client_id", "")
        self._client_secret = device_config.get("client_secret", "")
        self._access_token = device_config.get("access_token", "")
        self._refresh_token = device_config.get("refresh_token", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """OAuth2 flow — obtain or refresh access token."""
        self._client_id = credentials.get("client_id", self._client_id)
        self._client_secret = credentials.get("client_secret", self._client_secret)
        self._access_token = credentials.get("access_token", self._access_token)
        self._refresh_token = credentials.get("refresh_token", self._refresh_token)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            if self._refresh_token and not self._access_token:
                return await self._refresh_access_token()
            # Validate existing token
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with self._session.get(
                f"{BASE_URL}/api/v1/thermostats",
                headers=headers,
            ) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("EmersonSensiPlugin: OAuth token valid")
                elif self._refresh_token:
                    return await self._refresh_access_token()
                else:
                    logger.warning("EmersonSensiPlugin: auth failed: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("EmersonSensiPlugin: authenticate error: %s", exc)
            return False

    async def _refresh_access_token(self) -> bool:
        """Refresh OAuth2 access token."""
        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
            async with self._session.post(AUTH_URL, data=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._access_token = data.get("access_token", "")
                    self._refresh_token = data.get("refresh_token", self._refresh_token)
                    self._connected = bool(self._access_token)
                    logger.info("EmersonSensiPlugin: token refreshed")
                    return self._connected
                logger.warning("EmersonSensiPlugin: refresh failed: %s", resp.status)
                return False
        except Exception as exc:
            logger.error("EmersonSensiPlugin: refresh error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET thermostat status."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with self._session.get(
                f"{BASE_URL}/api/v1/thermostats/{self.device_id}",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = _translate_from_sensi(data)
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="emerson_sensi",
                        model=data.get("model", "sensi_thermostat"),
                        device_type="thermostat",
                        online=True,
                        state=state,
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("EmersonSensiPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("EmersonSensiPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST thermostat update."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        sensi_payload = _translate_to_sensi(payload)
        if not sensi_payload:
            logger.warning("EmersonSensiPlugin: empty translated payload")
            return False
        try:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with self._session.post(
                f"{BASE_URL}/api/v1/thermostats/{self.device_id}/settings",
                headers=headers,
                json=sensi_payload,
            ) as resp:
                success = 200 <= resp.status < 300
                logger.info(
                    "EmersonSensiPlugin: set_state -> %s (success=%s)",
                    sensi_payload,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("EmersonSensiPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("EmersonSensiPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="emerson_sensi",
            model=self.model,
            device_type="thermostat",
            online=False,
            state={},
            last_updated=time.time(),
        )
