"""Google Nest thermostat/camera plugin — Smart Device Management API."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import ThermostatPayload, CameraPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://smartdevicemanagement.googleapis.com/v1"


def _translate_trait_command(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Translate standard payload to Nest SDM trait-based executeCommand."""
    commands = []
    mode = payload.get("mode")
    target_temp = payload.get("target_temp")
    power = payload.get("power")

    if mode is not None:
        commands.append({
            "command": "sdm.devices.commands.ThermostatMode.SetMode",
            "params": {"mode": mode.upper()},
        })
    if target_temp is not None:
        commands.append({
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
            "params": {"heatCelsius": target_temp},
        })
    if power is not None:
        commands.append({
            "command": "sdm.devices.commands.CameraLiveStream.GenerateRtspStream",
            "params": {},
        })
    return commands[0] if commands else None


class NestPlugin(BaseDriver):
    """Google Nest Smart Device Management API plugin driver.

    Supports thermostats and cameras via REST API with OAuth2.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._token = device_config.get("token", "")
        self._project_id = device_config.get("project_id", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Validate OAuth2 bearer token with a test request."""
        self._token = credentials.get("token", self._token)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            headers = {"Authorization": f"Bearer {self._token}"}
            url = f"{BASE_URL}/enterprises/{self._project_id}/devices"
            async with self._session.get(url, headers=headers) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("NestPlugin: OAuth token validated")
                else:
                    logger.warning("NestPlugin: OAuth validation failed: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("NestPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET /enterprises/{project_id}/devices/{device_id}."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {"Authorization": f"Bearer {self._token}"}
        url = f"{BASE_URL}/enterprises/{self._project_id}/devices/{self.device_id}"
        try:
            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    traits = data.get("traits", {})
                    mode = traits.get(
                        "sdm.devices.traits.ThermostatMode", {}
                    ).get("mode", "off")
                    temp_trait = traits.get(
                        "sdm.devices.traits.ThermostatTemperatureSetpoint", {}
                    )
                    heat_celsius = temp_trait.get("heatCelsius")
                    amb_trait = traits.get(
                        "sdm.devices.traits.Temperature", {}
                    )
                    ambient = amb_trait.get("ambientTemperatureCelsius")
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="nest",
                        model=data.get("type", "nest_device"),
                        device_type=self.device_type,
                        online=True,
                        state={
                            "mode": mode.lower() if mode else "off",
                            "target_temp": heat_celsius,
                            "current_temp": ambient,
                            "display_name": data.get("parentRelations", [{}])[0].get("displayName", ""),
                        },
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("NestPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("NestPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST executeCommand with trait-based commands."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        command = _translate_trait_command(payload)
        if command is None:
            logger.warning("NestPlugin: no translatable command in payload %s", payload)
            return False
        url = (
            f"{BASE_URL}/enterprises/{self._project_id}"
            f"/devices/{self.device_id}:executeCommand"
        )
        body = {"command": command["command"], "params": command.get("params", {})}
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with self._session.post(url, headers=headers, json=body) as resp:
                success = 200 <= resp.status < 300
                logger.info(
                    "NestPlugin: set_state -> %s (success=%s)", command, success
                )
                return success
        except Exception as exc:
            logger.error("NestPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("NestPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="nest",
            model=self.model,
            device_type=self.device_type,
            online=False,
            state={},
            last_updated=time.time(),
        )
