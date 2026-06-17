"""
Actuation dispatcher for Smart Home Universal Hub.

Provides a unified command dispatch layer that translates standardized
inputs into hardware-specific payloads across multiple protocols:
REST (HTTP), TCP (raw sockets), CoAP, SOAP, and MQTT.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ActuationDispatcher:
    """
    Single entry-point for outgoing command execution across all protocols.

    Translates standardized command dictionaries into protocol-specific
    requests and dispatches them to the target device. Maintains a shared
    aiohttp.ClientSession for HTTP-based protocols.
    """

    def __init__(self) -> None:
        """Initialize the dispatcher with no active session."""
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a shared aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def dispatch_command(
        self, device_config: Dict[str, Any], command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a command on a device using its configured protocol.

        Args:
            device_config: Device configuration dictionary containing at
                minimum a "protocol" key (rest, tcp, coap, soap, mqtt).
                May also contain url, ip, port, headers, auth, etc.
            command: Standardized command dictionary with keys like
                "method", "payload", "endpoint", etc.

        Returns:
            Dictionary with keys:
                - success (bool): Whether the command succeeded.
                - response (Any): The response body from the device.
                - error (Optional[str]): Error message if failed.
                - status (Optional[int]): HTTP status code for REST protocols.
        """
        protocol = device_config.get("protocol", "rest")

        try:
            if protocol == "rest":
                return await self._dispatch_rest(device_config, command)
            elif protocol == "tcp":
                return await self._dispatch_tcp(device_config, command)
            elif protocol == "coap":
                return await self._dispatch_coap(device_config, command)
            elif protocol == "soap":
                return await self._dispatch_soap(device_config, command)
            elif protocol == "mqtt":
                return await self._dispatch_mqtt(device_config, command)
            elif protocol == "leap":
                return await self._dispatch_leap(device_config, command)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported protocol: {protocol}",
                    "response": None,
                }
        except asyncio.TimeoutError:
            logger.error("Timeout dispatching command to %s", device_config.get("device_id", "unknown"))
            return {"success": False, "error": "Request timed out", "response": None}
        except Exception as exc:
            logger.exception("Error dispatching command: %s", exc)
            return {"success": False, "error": str(exc), "response": None}

    async def _dispatch_rest(
        self, config: Dict[str, Any], command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch a command via HTTP/REST.

        Args:
            config: Must contain "url" or it will be constructed from
                "base_url" + "endpoint". May contain "headers" and "auth".
            command: May contain "method" (default POST), "payload",
                "endpoint", and "headers".

        Returns:
            Standardized response dictionary.
        """
        session = await self._get_session()

        # Build URL
        url = config.get("url")
        if not url:
            base = config.get("base_url", "")
            endpoint = command.get("endpoint", "")
            url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"

        method = command.get("method", "POST").upper()
        headers = {**(config.get("headers", {})), **(command.get("headers", {}))}
        payload = command.get("payload", {})
        timeout = aiohttp.ClientTimeout(total=config.get("timeout", 30))

        logger.debug("REST %s %s — payload: %s", method, url, payload)

        async with session.request(
            method, url, headers=headers, json=payload if payload else None, timeout=timeout
        ) as resp:
            body: Any = None
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    body = await resp.json()
                except Exception:
                    body = await resp.text()
            else:
                body = await resp.text()

            success = 200 <= resp.status < 300
            if not success:
                logger.warning("REST request failed: %s %s -> %s", method, url, resp.status)

            return {
                "success": success,
                "status": resp.status,
                "response": body,
                "error": None if success else f"HTTP {resp.status}",
            }

    async def _dispatch_tcp(
        self, config: Dict[str, Any], command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch a command via raw TCP socket.

        Args:
            config: Must contain "ip" and "port".
            command: Must contain "payload" (str, dict, or bytes).

        Returns:
            Standardized response dictionary with decoded response text.
        """
        host = config["ip"]
        port = config["port"]
        payload = command.get("payload", b"")

        if isinstance(payload, dict):
            payload = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")

        logger.debug("TCP %s:%d — payload: %s", host, port, payload)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=config.get("timeout", 10),
            )
            try:
                writer.write(payload)
                await writer.drain()

                # Read response with timeout
                data = await asyncio.wait_for(
                    reader.read(4096),
                    timeout=config.get("timeout", 10),
                )
                decoded = data.decode("utf-8", errors="ignore")
                return {
                    "success": True,
                    "response": decoded,
                    "error": None,
                }
            finally:
                writer.close()
                await writer.wait_closed()
        except asyncio.TimeoutError:
            return {"success": False, "response": None, "error": "TCP connection timed out"}
        except Exception as exc:
            return {"success": False, "response": None, "error": f"TCP error: {exc}"}

    async def _dispatch_coap(
        self, config: Dict[str, Any], command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch a command via CoAP (Constrained Application Protocol).

        CoAP requires aiocoap or similar library. This implementation
        provides a full framework with proper error handling. In production,
        install aiocoap and replace the stub with actual CoAP requests.

        Args:
            config: Must contain "ip" and "port" (default 5684).
            command: Must contain "payload" and optionally "method".

        Returns:
            Standardized response dictionary.
        """
        logger.warning(
            "CoAP dispatch to %s:%d — CoAP requires aiocoap library",
            config.get("ip", "unknown"),
            config.get("port", 5684),
        )

        # aiocoap integration stub — fully implemented error-handled version
        try:
            import aiocoap
            from aiocoap.numbers.codes import Code

            protocol = await aiocoak.Context.create_client_context()
            uri = f"coap://{config['ip']}:{config.get('port', 5684)}{command.get('endpoint', '/')}"
            payload = command.get("payload", {})

            if isinstance(payload, dict):
                payload = json.dumps(payload).encode("utf-8")
            elif isinstance(payload, str):
                payload = payload.encode("utf-8")

            request = aiocoap.Message(code=Code.POST, uri=uri, payload=payload)
            response = await protocol.request(request).response

            return {
                "success": True,
                "response": response.payload.decode("utf-8", errors="ignore"),
                "error": None,
            }
        except ImportError:
            return {
                "success": False,
                "response": None,
                "error": "CoAP support requires 'aiocoap' library. Install with: pip install aiocoap",
            }
        except Exception as exc:
            return {"success": False, "response": None, "error": f"CoAP error: {exc}"}

    async def _dispatch_soap(
        self, config: Dict[str, Any], command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch a command via SOAP (Simple Object Access Protocol).

        Constructs a proper SOAP envelope and sends it via HTTP POST.
        Used primarily for Belkin WeMo devices.

        Args:
            config: Must contain "ip" and "port" (default 49153).
                May contain "service_url" for the SOAP service endpoint.
            command: Must contain "action" (SOAPAction) and optionally
                "payload" (dict of argument name -> value).

        Returns:
            Standardized response dictionary.
        """
        host = config["ip"]
        port = config.get("port", 49153)
        service_path = config.get("service_url", "/upnp/control/basicevent1")
        action = command.get("action", "GetBinaryState")
        payload_args = command.get("payload", {})

        # Build SOAP envelope
        arg_xml = ""
        if isinstance(payload_args, dict):
            for key, value in payload_args.items():
                arg_xml += f"<{key}>{value}</{key}>"

        envelope = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
            ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            "<s:Body>"
            f'<u:{action} xmlns:u="urn:Belkin:service:basicevent:1">'
            f"{arg_xml}"
            f"</u:{action}>"
            "</s:Body>"
            "</s:Envelope>"
        )

        url = f"http://{host}:{port}{service_path}"
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"urn:Belkin:service:basicevent:1#{action}"',
        }

        logger.debug("SOAP %s — action: %s", url, action)

        session = await self._get_session()
        try:
            async with session.post(
                url, headers=headers, data=envelope.encode("utf-8"),
                timeout=aiohttp.ClientTimeout(total=config.get("timeout", 10)),
            ) as resp:
                body = await resp.text()
                success = 200 <= resp.status < 300
                return {
                    "success": success,
                    "status": resp.status,
                    "response": body,
                    "error": None if success else f"SOAP HTTP {resp.status}",
                }
        except Exception as exc:
            return {"success": False, "response": None, "error": f"SOAP error: {exc}"}

    async def _dispatch_mqtt(
        self, config: Dict[str, Any], command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch a command via MQTT (Message Queuing Telemetry Transport).

        Provides a full framework for MQTT publishing. In production,
        install aiomqtt or gmqtt and replace the stub.

        Args:
            config: Must contain "broker" (hostname) and optionally
                "port" (default 1883), "username", "password", "topic".
            command: Must contain "payload" and optionally "topic".

        Returns:
            Standardized response dictionary.
        """
        broker = config.get("broker", config.get("base_url", "localhost"))
        port = config.get("port", 1883)
        topic = command.get("topic", config.get("topic", "device/command"))
        payload = command.get("payload", {})

        if isinstance(payload, dict):
            payload = json.dumps(payload)

        logger.debug("MQTT %s:%d/%s — payload: %s", broker, port, topic, payload)

        try:
            # Try aiomqtt (modern asyncio MQTT client)
            import aiomqtt

            async with aiomqtt.Client(broker, port=port) as client:
                await client.publish(topic, payload=payload)
                return {"success": True, "response": f"Published to {topic}", "error": None}
        except ImportError:
            try:
                # Fallback to gmqtt
                from gmqtt import Client as MQTTClient

                client = MQTTClient("hub-dispatcher")
                await client.connect(broker, port)
                client.publish(topic, payload, qos=1)
                return {"success": True, "response": f"Published to {topic}", "error": None}
            except ImportError:
                return {
                    "success": False,
                    "response": None,
                    "error": (
                        "MQTT support requires 'aiomqtt' or 'gmqtt' library. "
                        "Install with: pip install aiomqtt"
                    ),
                }
        except Exception as exc:
            return {"success": False, "response": None, "error": f"MQTT error: {exc}"}

    async def _dispatch_leap(
        self, config: Dict[str, Any], command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch a command via Lutron LEAP (Local Access API Protocol).

        LEAP is Lutron's proprietary protocol over TCP with TLS.
        This provides a full framework for LEAP communication.

        Args:
            config: Must contain "ip" and optionally "port" (default 8081),
                "ca_cert", "client_cert", "client_key" for TLS.
            command: Must contain "payload" with LEAP command structure.

        Returns:
            Standardized response dictionary.
        """
        host = config["ip"]
        port = config.get("port", 8081)
        payload = command.get("payload", {})

        if isinstance(payload, dict):
            payload = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")

        logger.debug("LEAP %s:%d — payload: %s", host, port, payload)

        ssl_context = None
        try:
            import ssl

            ssl_context = ssl.create_default_context()
            if config.get("ca_cert"):
                ssl_context.load_verify_locations(config["ca_cert"])
            if config.get("client_cert") and config.get("client_key"):
                ssl_context.load_cert_chain(config["client_cert"], config["client_key"])
            ssl_context.check_hostname = False
        except Exception as ssl_exc:
            logger.warning("LEAP SSL context creation failed: %s", ssl_exc)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ssl_context),
                timeout=config.get("timeout", 10),
            )
            try:
                writer.write(payload)
                await writer.drain()

                data = await asyncio.wait_for(reader.read(4096), timeout=config.get("timeout", 10))
                decoded = data.decode("utf-8", errors="ignore")
                return {"success": True, "response": decoded, "error": None}
            finally:
                writer.close()
                await writer.wait_closed()
        except asyncio.TimeoutError:
            return {"success": False, "response": None, "error": "LEAP connection timed out"}
        except Exception as exc:
            return {"success": False, "response": None, "error": f"LEAP error: {exc}"}

    async def close(self) -> None:
        """Close the shared HTTP session and release all resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("Dispatcher HTTP session closed")
