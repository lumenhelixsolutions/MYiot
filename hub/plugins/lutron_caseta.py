"""Lutron Caseta plugin — LEAP protocol over SSL."""

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Dict, Optional

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartLightPayload, SmartPlugPayload

logger = logging.getLogger(__name__)

LEAP_PORT = 8081


def _translate_to_leap(device_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard payload to LEAP protocol command."""
    leap: Dict[str, Any] = {}
    if device_type in ("light", "plug"):
        power = payload.get("power")
        if power is not None:
            leap["ZoneStatus"] = {"Level": 100 if power else 0}
        brightness = payload.get("brightness")
        if brightness is not None:
            level = int(max(0, min(100, brightness)))
            leap["ZoneStatus"] = {"Level": level}
    return leap


def _translate_from_leap(device_type: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse LEAP response into standardized state."""
    state = {}
    zone_status = raw.get("ZoneStatus", {})
    level = zone_status.get("Level", 0)
    state["power"] = level > 0
    state["brightness"] = level
    state["switched_level"] = zone_status.get("SwitchedLevel")
    return state


class LutronCasetaPlugin(BaseDriver):
    """Lutron Caseta plugin driver.

    Communicates via the LEAP (Lutron Extensible Application Protocol)
    over an SSL-encrypted TCP connection to the Smart Bridge.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._bridge_ip = device_config.get("bridge_ip", "192.168.1.100")
        self._bridge_port = device_config.get("bridge_port", LEAP_PORT)
        self._cert_file = device_config.get("cert_file", "")
        self._key_file = device_config.get("key_file", "")
        self._ca_file = device_config.get("ca_file", "")
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._ssl_context: Optional[ssl.SSLContext] = None

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Certificate-based authentication with the Smart Bridge."""
        self._cert_file = credentials.get("cert_file", self._cert_file)
        self._key_file = credentials.get("key_file", self._key_file)
        self._ca_file = credentials.get("ca_file", self._ca_file)
        try:
            self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            if self._ca_file:
                self._ssl_context.load_verify_locations(self._ca_file)
            else:
                self._ssl_context.check_hostname = False
                self._ssl_context.verify_mode = ssl.CERT_NONE
            if self._cert_file and self._key_file:
                self._ssl_context.load_cert_chain(self._cert_file, self._key_file)
            # Test connection
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._bridge_ip,
                    self._bridge_port,
                    ssl=self._ssl_context,
                ),
                timeout=5.0,
            )
            self._connected = True
            logger.info("LutronCasetaPlugin: SSL connection to %s established", self._bridge_ip)
            return True
        except Exception as exc:
            logger.error("LutronCasetaPlugin: authenticate error: %s", exc)
            self._connected = False
            return False

    async def _send_leap(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send a LEAP command and read response."""
        if not self._writer or self._writer.is_closing():
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        self._bridge_ip,
                        self._bridge_port,
                        ssl=self._ssl_context,
                    ),
                    timeout=5.0,
                )
            except Exception as exc:
                logger.error("LutronCasetaPlugin: reconnect failed: %s", exc)
                return {}
        try:
            msg = json.dumps(command) + "\n"
            self._writer.write(msg.encode("utf-8"))
            await self._writer.drain()
            resp = await asyncio.wait_for(self._reader.readline(), timeout=5.0)
            if resp:
                return json.loads(resp.decode("utf-8"))
            return {}
        except asyncio.TimeoutError:
            logger.error("LutronCasetaPlugin: LEAP command timeout")
            return {}
        except Exception as exc:
            logger.error("LutronCasetaPlugin: LEAP command error: %s", exc)
            return {}

    async def get_state(self) -> DeviceState:
        """Send LEAP read command for device zone."""
        try:
            command = {
                "CommuniqueType": "ReadRequest",
                "Header": {
                    "Url": f"/zone/{self.device_id}/status",
                },
            }
            resp = await self._send_leap(command)
            body = resp.get("Body", {})
            state = _translate_from_leap(self.device_type, body)
            return DeviceState(
                device_id=self.device_id,
                manufacturer="lutron_caseta",
                model="caseta_switch",
                device_type=self.device_type,
                online=True,
                state=state,
                last_updated=time.time(),
            )
        except Exception as exc:
            logger.error("LutronCasetaPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Send LEAP write command to control device."""
        leap_payload = _translate_to_leap(self.device_type, payload)
        if not leap_payload:
            logger.warning("LutronCasetaPlugin: empty translated payload")
            return False
        try:
            level = leap_payload.get("ZoneStatus", {}).get("Level", 0)
            command = {
                "CommuniqueType": "CreateRequest",
                "Header": {
                    "Url": f"/zone/{self.device_id}/commandprocessor",
                },
                "Body": {
                    "Command": {
                        "CommandType": "GoToLevel",
                        "Parameter": [{"Type": "Level", "Value": level}],
                    }
                },
            }
            resp = await self._send_leap(command)
            status = resp.get("Header", {}).get("StatusCode", "")
            success = status in ("200 OK", "201 Created")
            logger.info(
                "LutronCasetaPlugin: set_state -> level=%s (success=%s)",
                level,
                success,
            )
            return success
        except Exception as exc:
            logger.error("LutronCasetaPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Close SSL connection."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        self._connected = False
        logger.info("LutronCasetaPlugin: disconnected")

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="lutron_caseta",
            model=self.model,
            device_type=self.device_type,
            online=False,
            state={},
            last_updated=time.time(),
        )
