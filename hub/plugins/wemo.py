"""Belkin Wemo smart plug plugin — SOAP/XML over HTTP."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartPlugPayload

logger = logging.getLogger(__name__)

# SOAP envelope templates
_GET_BINARY_STATE_ENVELOPE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:GetBinaryState xmlns:u="urn:Belkin:service:basicevent:1">
    </u:GetBinaryState>
  </s:Body>
</s:Envelope>"""

_SET_BINARY_STATE_ENVELOPE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetBinaryState xmlns:u="urn:Belkin:service:basicevent:1">
      <BinaryState>{state}</BinaryState>
    </u:SetBinaryState>
  </s:Body>
</s:Envelope>"""

_SOAP_HEADERS = {
    "Content-Type": 'text/xml; charset="utf-8"',
    "SOAPACTION": '"urn:Belkin:service:basicevent:1#GetBinaryState"',
}

_SET_SOAP_HEADERS = {
    "Content-Type": 'text/xml; charset="utf-8"',
    "SOAPACTION": '"urn:Belkin:service:basicevent:1#SetBinaryState"',
}


class WemoPlugin(BaseDriver):
    """Belkin Wemo smart plug plugin driver.

    Communicates via SOAP/XML over HTTP on port 49153.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._ip = device_config.get("ip", "192.168.1.100")
        self._port = device_config.get("port", 49153)
        self._control_url = f"http://{self._ip}:{self._port}/upnp/control/basicevent1"

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Wemo devices require no authentication."""
        logger.info("WemoPlugin: authenticate() — no auth required for %s", self._ip)
        self._connected = True
        return True

    async def get_state(self) -> DeviceState:
        """Send GetBinaryState SOAP action and parse response."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        try:
            async with self._session.post(
                self._control_url,
                data=_GET_BINARY_STATE_ENVELOPE,
                headers=_SOAP_HEADERS,
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    # Parse BinaryState from XML
                    state_val = self._extract_binary_state(text)
                    power = state_val == "1"
                    return DeviceState(
                        device_id=self.device_id,
                        manufacturer="wemo",
                        model="wemo_plug",
                        device_type="plug",
                        online=True,
                        state={
                            "power": power,
                            "binary_state": state_val,
                        },
                        last_updated=time.time(),
                    )
                else:
                    logger.warning("WemoPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("WemoPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Send SetBinaryState SOAP action."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        power = payload.get("power")
        if power is None:
            logger.warning("WemoPlugin: set_state requires power field")
            return False
        state_val = 1 if power else 0
        envelope = _SET_BINARY_STATE_ENVELOPE.format(state=state_val)
        try:
            async with self._session.post(
                self._control_url,
                data=envelope,
                headers=_SET_SOAP_HEADERS,
            ) as resp:
                success = resp.status == 200
                logger.info(
                    "WemoPlugin: set_state power=%s -> success=%s",
                    power,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("WemoPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("WemoPlugin: session closed")
        self._connected = False

    @staticmethod
    def _extract_binary_state(xml_text: str) -> str:
        """Extract BinaryState value from SOAP XML response."""
        import re
        match = re.search(r"<BinaryState>(\d+)</BinaryState>", xml_text)
        if match:
            return match.group(1)
        return "0"

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="wemo",
            model=self.model,
            device_type="plug",
            online=False,
            state={},
            last_updated=time.time(),
        )
