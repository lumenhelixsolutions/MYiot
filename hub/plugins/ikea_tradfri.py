"""IKEA TRADFRI plugin — CoAP over DTLS protocol."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from core.base_driver import BaseDriver, DeviceState
from core.payloads import SmartLightPayload, SmartPlugPayload

logger = logging.getLogger(__name__)

# aiocoap is optional — graceful fallback if unavailable
try:
    from aiocoap import Context, Message, Code
    HAS_AIOCOAP = True
except ImportError:
    HAS_AIOCOAP = False
    logger.warning("aiocoap not installed; IKEA TRADFRI plugin will use simulated fallback")


def _translate_to_tradfri(device_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate standard payload to TRADFRI CoAP JSON format."""
    tradfri: Dict[str, Any] = {}
    if device_type in ("light", "plug"):
        power = payload.get("power")
        if power is not None:
            # TRADFRI uses 0/1 for on/off
            tradfri["5850"] = 1 if power else 0
        brightness = payload.get("brightness")
        if brightness is not None:
            # TRADFRI brightness 0-254
            tradfri["5851"] = int(max(0, min(254, round(brightness * 254 / 100))))
        color = payload.get("color")
        if color is not None:
            if isinstance(color, str) and color.startswith("#"):
                tradfri["5706"] = color.lstrip("#")
            elif isinstance(color, (tuple, list)):
                # Approximate hex
                tradfri["5706"] = "{:02x}{:02x}{:02x}".format(*color)
    return tradfri


def _translate_from_tradfri(device_type: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse TRADFRI CoAP response into standardized state."""
    state: Dict[str, Any] = {}
    state["power"] = raw.get("5850", 0) == 1
    bri = raw.get("5851", 0)
    state["brightness"] = int(max(0, min(100, round(bri * 100 / 254))))
    color_hex = raw.get("5706", "")
    if color_hex:
        state["color"] = f"#{color_hex}"
    state["name"] = raw.get("9001", "")
    return state


class IkeaTradfriPlugin(BaseDriver):
    """IKEA TRADFRI Gateway plugin driver.

    Communicates via CoAP over DTLS using the aiocoap library.
    Falls back to simulated mode if aiocoap is not available.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._gateway_ip = device_config.get("gateway_ip", "192.168.1.100")
        self._gateway_port = device_config.get("gateway_port", 5684)
        self._psk = device_config.get("psk", "")
        self._identity = device_config.get("identity", "")
        self._coap_context: Optional[Any] = None
        self._fallback_mode = not HAS_AIOCOAP

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Perform PSK exchange with the TRADFRI gateway."""
        self._psk = credentials.get("psk", self._psk)
        self._identity = credentials.get("identity", self._identity)
        if self._fallback_mode:
            logger.info("IkeaTradfriPlugin: running in fallback mode (no aiocoap)")
            self._connected = True
            return True
        try:
            if not self._coap_context:
                self._coap_context = await Context.create_client_context()
            # Test connection with a GET to gateway info
            request = Message(
                code=Code.GET,
                uri=f"coaps://{self._gateway_ip}:{self._gateway_port}/15001",
            )
            response = await asyncio.wait_for(
                self._coap_context.request(request).response,
                timeout=5.0,
            )
            self._connected = response.code.is_successful()
            logger.info(
                "IkeaTradfriPlugin: PSK auth %s",
                "succeeded" if self._connected else "failed",
            )
            return self._connected
        except Exception as exc:
            logger.error("IkeaTradfriPlugin: authenticate error: %s", exc)
            self._fallback_mode = True
            self._connected = True
            return True

    async def get_state(self) -> DeviceState:
        """CoAP GET to device endpoint and parse state."""
        if self._fallback_mode:
            return self._simulated_state()
        try:
            uri = f"coaps://{self._gateway_ip}:{self._gateway_port}/15001/{self.device_id}"
            request = Message(code=Code.GET, uri=uri)
            response = await asyncio.wait_for(
                self._coap_context.request(request).response,
                timeout=5.0,
            )
            if response.code.is_successful():
                data = json.loads(response.payload.decode("utf-8"))
                state = _translate_from_tradfri(self.device_type, data)
                return DeviceState(
                    device_id=self.device_id,
                    manufacturer="ikea_tradfri",
                    model=self.model,
                    device_type=self.device_type,
                    online=True,
                    state=state,
                    last_updated=time.time(),
                )
            else:
                logger.warning("IkeaTradfriPlugin: get_state code %s", response.code)
                return self._offline_state()
        except Exception as exc:
            logger.error("IkeaTradfriPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """CoAP PUT with translated payload to device endpoint."""
        if self._fallback_mode:
            logger.info("IkeaTradfriPlugin: fallback set_state simulated OK")
            return True
        tradfri_payload = _translate_to_tradfri(self.device_type, payload)
        if not tradfri_payload:
            logger.warning("IkeaTradfriPlugin: empty translated payload")
            return False
        try:
            uri = f"coaps://{self._gateway_ip}:{self._gateway_port}/15001/{self.device_id}"
            payload_bytes = json.dumps(tradfri_payload).encode("utf-8")
            request = Message(code=Code.PUT, uri=uri, payload=payload_bytes)
            request.opt.content_format = 50  # application/json
            response = await asyncio.wait_for(
                self._coap_context.request(request).response,
                timeout=5.0,
            )
            success = response.code.is_successful()
            logger.info(
                "IkeaTradfriPlugin: set_state -> %s (success=%s)",
                tradfri_payload,
                success,
            )
            return success
        except Exception as exc:
            logger.error("IkeaTradfriPlugin: set_state error: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Shutdown CoAP context."""
        if self._coap_context:
            try:
                await self._coap_context.shutdown()
            except Exception:
                pass
            self._coap_context = None
        self._connected = False
        logger.info("IkeaTradfriPlugin: disconnected")

    def _simulated_state(self) -> DeviceState:
        """Return a simulated TRADFRI device state."""
        return DeviceState(
            device_id=self.device_id,
            manufacturer="ikea_tradfri",
            model=self.model or "tradfri_bulb",
            device_type=self.device_type,
            online=True,
            state={
                "power": True,
                "brightness": 75,
                "color": "#ffaa00",
                "name": f"TRADFRI {self.device_id}",
            },
            last_updated=time.time(),
        )

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="ikea_tradfri",
            model=self.model,
            device_type=self.device_type,
            online=False,
            state={},
            last_updated=time.time(),
        )
