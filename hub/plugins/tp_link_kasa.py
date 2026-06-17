"""TP-Link Kasa smart plug plugin — local TCP on port 9999 with XOR encryption."""

import asyncio
import json
import logging
import struct
import time
from typing import Any, Dict, Optional

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartPlugPayload

logger = logging.getLogger(__name__)


def _xor_encrypt(plaintext: str, key: int = 0xAB) -> bytes:
    """Encrypt data using Kasa protocol XOR cipher."""
    data = plaintext.encode("utf-8")
    encrypted = bytearray()
    for byte in data:
        encrypted.append(byte ^ key)
        key = encrypted[-1]
    # Prepend 4-byte big-endian length header
    return struct.pack(">I", len(data)) + bytes(encrypted)


def _xor_decrypt(data: bytes, key: int = 0xAB) -> str:
    """Decrypt Kasa protocol XOR-encrypted response."""
    if len(data) < 4:
        return "{}"
    payload = data[4:]  # Strip length header
    decrypted = bytearray()
    for byte in payload:
        decrypted.append(byte ^ key)
        key = byte
    return decrypted.decode("utf-8", errors="ignore")


class TpLinkKasaPlugin(BaseDriver):
    """TP-Link Kasa smart plug plugin driver.

    Uses local TCP communication on port 9999 with XOR-encrypted JSON payloads.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._ip = device_config.get("ip", "192.168.1.100")
        self._port = device_config.get("port", 9999)
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Kasa devices require no authentication on local network."""
        logger.info("TpLinkKasaPlugin: authenticate() — no auth required for %s", self._ip)
        self._connected = True
        return True

    async def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send an encrypted command and return the decrypted response."""
        payload = json.dumps(command)
        encrypted = _xor_encrypt(payload)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._ip, self._port),
                timeout=5.0,
            )
            try:
                writer.write(encrypted)
                await writer.drain()
                # Read response: 4-byte length header + payload
                header = await asyncio.wait_for(reader.read(4), timeout=5.0)
                if len(header) < 4:
                    return {}
                length = struct.unpack(">I", header)[0]
                encrypted_resp = await asyncio.wait_for(
                    reader.read(length), timeout=5.0
                )
                full_resp = header + encrypted_resp
                decrypted = _xor_decrypt(full_resp)
                return json.loads(decrypted)
            finally:
                writer.close()
                await writer.wait_closed()
        except asyncio.TimeoutError:
            logger.error("TpLinkKasaPlugin: timeout talking to %s:%s", self._ip, self._port)
            return {}
        except Exception as exc:
            logger.error("TpLinkKasaPlugin: command error: %s", exc)
            return {}

    async def get_state(self) -> DeviceState:
        """Send get_sysinfo command and parse response."""
        cmd = {"system": {"get_sysinfo": None}}
        resp = await self._send_command(cmd)
        sysinfo = resp.get("system", {}).get("get_sysinfo", {})
        relay_state = sysinfo.get("relay_state", 0)
        return DeviceState(
            device_id=self.device_id,
            manufacturer="tp_link_kasa",
            model=sysinfo.get("model", "kasa_plug"),
            device_type="plug",
            online=bool(sysinfo),
            state={
                "power": relay_state == 1,
                "relay_state": relay_state,
                "alias": sysinfo.get("alias", ""),
                "rssi": sysinfo.get("rssi"),
            },
            last_updated=time.time(),
        )

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Send set_relay_state command."""
        power = payload.get("power")
        if power is None:
            logger.warning("TpLinkKasaPlugin: set_state requires power field")
            return False
        state_val = 1 if power else 0
        cmd = {"system": {"set_relay_state": {"state": state_val}}}
        resp = await self._send_command(cmd)
        try:
            success = (
                resp.get("system", {})
                .get("set_relay_state", {})
                .get("err_code", -1)
                == 0
            )
            logger.info(
                "TpLinkKasaPlugin: set_state power=%s -> success=%s",
                power,
                success,
            )
            return success
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Close any open socket."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        self._connected = False
        logger.info("TpLinkKasaPlugin: disconnected")
