"""Sonoff/eWeLink plugin — REST API local mode."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartPlugPayload

logger = logging.getLogger(__name__)


def _translate_to_sonoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard payload to Sonoff zeroconf format."""
    sonoff: Dict[str, Any] = {}
    power = payload.get("power")
    if power is not None:
        sonoff["switch"] = "on" if power else "off"
    return sonoff


def _translate_from_sonoff(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Sonoff device state into standardized format."""
    state = {}
    data = raw.get("data", raw)
    switch_val = data.get("switch", "off")
    state["power"] = switch_val in ("on", True, 1)
    state["rssi"] = data.get("signalStrength", data.get("rssi"))
    state["startup"] = data.get("startup", "off")
    state["pulse"] = data.get("pulse", "off")
    state["pulse_width"] = data.get("pulseWidth", 0)
    return state


class SonoffPlugin(BaseDriver):
    """Sonoff/eWeLink plugin driver (local REST mode).

    Communicates directly with Sonoff devices on the local network
    via the zeroconf REST endpoint on port 8081.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._ip = device_config.get("ip", "192.168.1.100")
        self._port = device_config.get("port", 8081)
        self._device_id = device_config.get("device_id", "")
        self._api_key = device_config.get("api_key", "")
        self._base_url = f"http://{self._ip}:{self._port}/zeroconf"

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Validate bearer token via info request."""
        self._api_key = credentials.get("api_key", self._api_key)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            payload = {"deviceid": self._device_id, "data": {}}
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with self._session.post(
                f"{self._base_url}/info",
                json=payload,
                headers=headers,
            ) as resp:
                self._connected = resp.status == 200
                if self._connected:
                    logger.info("SonoffPlugin: authenticated to %s", self._ip)
                else:
                    logger.warning("SonoffPlugin: auth failed: %s", resp.status)
                return self._connected
        except Exception as exc:
            logger.error("SonoffPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET device state via zeroconf info endpoint."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        try:
            payload = {"deviceid": self._device_id, "data": {}}
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with self._session.post(
                f"{self._base_url}/info",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = _translate_from_sonoff(data)
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="sonoff",
                        model=data.get("data", {}).get("model", "sonoff_basic"),
                        device_type="plug",
                        online=True,
                        state=state,
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("SonoffPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("SonoffPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST zeroconf switch command."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        sonoff_payload = _translate_to_sonoff(payload)
        if not sonoff_payload:
            logger.warning("SonoffPlugin: empty translated payload")
            return False
        try:
            body = {
                "deviceid": self._device_id,
                "data": sonoff_payload,
            }
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with self._session.post(
                f"{self._base_url}/switch",
                json=body,
                headers=headers,
            ) as resp:
                success = resp.status == 200
                logger.info(
                    "SonoffPlugin: set_state -> %s (success=%s)",
                    sonoff_payload,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("SonoffPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("SonoffPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="sonoff",
            model=self.model,
            device_type="plug",
            online=False,
            state={},
            last_updated=time.time(),
        )
