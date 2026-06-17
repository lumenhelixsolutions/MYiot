"""Ecobee thermostat plugin — REST API with PIN-based OAuth."""

import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import ThermostatPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ecobee.com"


def _translate_to_ecobee(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Translate standard ThermostatPayload to Ecobee API thermostat update."""
    settings = {}
    mode = payload.get("mode")
    if mode is not None:
        settings["hvacMode"] = mode
    target_temp = payload.get("target_temp")
    if target_temp is not None:
        # Ecobee uses Fahrenheit by default; assume payload is in Fahrenheit
        settings["heatTemp"] = int(target_temp * 10)
        settings["coolTemp"] = int(target_temp * 10)
    return [{"type": "setHold", "holdType": "indefinite", "params": settings}] if settings else []


def _translate_from_ecobee(thermostat: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Ecobee thermostat response into standardized state."""
    state = {}
    runtime = thermostat.get("runtime", {})
    settings = thermostat.get("settings", {})
    state["mode"] = settings.get("hvacMode", "off")
    state["target_temp"] = runtime.get("desiredHeat") / 10.0 if runtime.get("desiredHeat") else None
    state["current_temp"] = runtime.get("actualTemperature") / 10.0 if runtime.get("actualTemperature") else None
    state["humidity"] = runtime.get("actualHumidity")
    state["fan"] = settings.get("fan", "auto")
    return state


class EcobeePlugin(BaseDriver):
    """Ecobee thermostat plugin driver.

    Uses the Ecobee REST API with PIN-based OAuth2 authentication.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._api_key = device_config.get("api_key", "")
        self._access_token = device_config.get("access_token", "")
        self._refresh_token = device_config.get("refresh_token", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """OAuth2 flow — validate or refresh access token."""
        self._api_key = credentials.get("api_key", self._api_key)
        self._access_token = credentials.get("access_token", self._access_token)
        self._refresh_token = credentials.get("refresh_token", self._refresh_token)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            # Validate token by requesting thermostat summary
            headers = {"Authorization": f"Bearer {self._access_token}"}
            params = {
                "json": '{"selection":{"selectionType":"registered","selectionMatch":"","includeRuntime":true}}'
            }
            async with self._session.get(
                f"{BASE_URL}/1/thermostatSummary", headers=headers, params=params
            ) as resp:
                if resp.status == 200:
                    self._connected = True
                    logger.info("EcobeePlugin: OAuth token valid")
                    return True
                elif resp.status == 500 and self._refresh_token:
                    return await self._refresh_access_token()
                logger.warning("EcobeePlugin: auth failed: %s", resp.status)
                return False
        except Exception as exc:
            logger.error("EcobeePlugin: authenticate error: %s", exc)
            return False

    async def _refresh_access_token(self) -> bool:
        """Refresh OAuth2 access token using refresh token."""
        try:
            payload = {
                "grant_type": "refresh_token",
                "code": self._refresh_token,
                "client_id": self._api_key,
            }
            async with self._session.post(
                f"{BASE_URL}/token", data=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._access_token = data.get("access_token", "")
                    self._refresh_token = data.get("refresh_token", "")
                    self._connected = True
                    logger.info("EcobeePlugin: token refreshed")
                    return True
                logger.warning("EcobeePlugin: token refresh failed: %s", resp.status)
                return False
        except Exception as exc:
            logger.error("EcobeePlugin: refresh error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET thermostat summary and parse state."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        body = {
            "selection": {
                "selectionType": "thermostats",
                "selectionMatch": self.device_id,
                "includeRuntime": True,
                "includeSettings": True,
            }
        }
        try:
            async with self._session.get(
                f"{BASE_URL}/1/thermostat",
                headers=headers,
                json=body,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    thermostats = data.get("thermostatList", [])
                    if thermostats:
                        tstat = thermostats[0]
                        state = _translate_from_ecobee(tstat)
                        return DeviceState(
                            device_id=self.device_id,
                            manufacturer="ecobee",
                            model=tstat.get("modelNumber", "ecobee"),
                            device_type="thermostat",
                            online=True,
                            state=state,
                            last_updated=time.time(),
                        )
                    logger.warning("EcobeePlugin: thermostat %s not found", self.device_id)
                    return self._offline_state()
                else:
                    logger.warning("EcobeePlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("EcobeePlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST thermostat update commands."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        functions = _translate_to_ecobee(payload)
        if not functions:
            logger.warning("EcobeePlugin: empty translated payload")
            return False
        body = {
            "selection": {
                "selectionType": "thermostats",
                "selectionMatch": self.device_id,
            },
            "functions": functions,
        }
        headers = {"Authorization": f"Bearer {self._access_token}", "Content-Type": "application/json"}
        try:
            async with self._session.post(
                f"{BASE_URL}/1/thermostat",
                headers=headers,
                json=body,
            ) as resp:
                success = resp.status == 200
                logger.info(
                    "EcobeePlugin: set_state -> %s (success=%s)",
                    functions,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("EcobeePlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("EcobeePlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="ecobee",
            model=self.model,
            device_type="thermostat",
            online=False,
            state={},
            last_updated=time.time(),
        )
