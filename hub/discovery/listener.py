"""
Network discovery listener for Smart Home Universal Hub.

Provides UDP, mDNS, and SSDP listeners for device discovery broadcasts.
Catches real-time state changes and device announcements without active
polling. Supports callbacks for device_found and state_change events.
"""

import asyncio
import logging
import re
import socket
import struct
from typing import Callable, Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# SSDP constants
SSDP_MULTICAST_GROUP = "239.255.255.250"
SSDP_PORT = 1900
SSDP_BUFFER_SIZE = 2048

# Known manufacturer SSDP identifiers
SSDP_MANUFACTURER_PATTERNS = {
    "philips_hue": re.compile(r"Philips|Hue", re.IGNORECASE),
    "wemo": re.compile(r"Belkin|WeMo", re.IGNORECASE),
    "tp_link_kasa": re.compile(r"TP-Link|Kasa", re.IGNORECASE),
    "sonoff": re.compile(r"Sonoff|eWeLink", re.IGNORECASE),
    "lutron_caseta": re.compile(r"Lutron|Caseta", re.IGNORECASE),
    "ring": re.compile(r"Ring", re.IGNORECASE),
    "nest": re.compile(r"Nest", re.IGNORECASE),
    "ecobee": re.compile(r"Ecobee", re.IGNORECASE),
}

# Device type patterns from SSDP/USN strings
DEVICE_TYPE_PATTERNS = {
    "light": re.compile(r"light|lamp|bulb|dimmer", re.IGNORECASE),
    "plug": re.compile(r"plug|socket|switch|outlet", re.IGNORECASE),
    "camera": re.compile(r"camera|cam|doorbell", re.IGNORECASE),
    "thermostat": re.compile(r"thermostat|hvac|climate", re.IGNORECASE),
}


class NetworkDiscoveryListener:
    """
    UDP, mDNS, and SSDP listeners for device discovery broadcasts.

    Listens for device announcements on the local network via multiple
    discovery protocols and invokes callbacks when devices are found
    or their states change.
    """

    def __init__(
        self,
        on_device_found: Callable[[Dict[str, Any]], None],
        on_state_change: Callable[[Dict[str, Any]], None],
    ):
        """
        Initialize the discovery listener.

        Args:
            on_device_found: Callback invoked when a new device is discovered.
                Receives a dictionary with device details.
            on_state_change: Callback invoked when a known device's state changes.
                Receives a dictionary with updated device details.
        """
        self.on_device_found = on_device_found
        self.on_state_change = on_state_change
        self._listeners: List[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start all discovery listeners concurrently."""
        if self._running:
            logger.warning("Discovery listener already running")
            return

        self._running = True
        logger.info("Starting network discovery listeners...")

        self._listeners = [
            asyncio.create_task(
                self._ssdp_listener(), name="ssdp_listener"
            ),
            asyncio.create_task(
                self._mdns_listener(), name="mdns_listener"
            ),
            asyncio.create_task(
                self._udp_broadcast_listener(), name="udp_broadcast_listener"
            ),
        ]

        logger.info(
            "All discovery listeners started (%d tasks)", len(self._listeners)
        )

    async def stop(self) -> None:
        """Stop all discovery listeners and clean up resources."""
        if not self._running:
            return

        logger.info("Stopping network discovery listeners...")
        self._running = False

        for task in self._listeners:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.debug("Listener task cancellation error: %s", exc)

        self._listeners.clear()
        logger.info("Discovery listeners stopped")

    # ─── SSDP Listener ──────────────────────────────────────────────────────

    async def _ssdp_listener(self) -> None:
        """
        Listen for SSDP (Simple Service Discovery Protocol) broadcasts.

        Binds a UDP socket to port 1900 and joins the SSDP multicast
        group (239.255.255.250) to receive NOTIFY announcements and
        M-SEARCH responses from UPnP devices on the local network.
        """
        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to the SSDP port
            try:
                sock.bind(("0.0.0.0", SSDP_PORT))
            except OSError as bind_err:
                logger.warning(
                    "Cannot bind to SSDP port %d: %s. "
                    "SSDP discovery may not work (port may be in use).",
                    SSDP_PORT,
                    bind_err,
                )
                return

            # Join the multicast group
            try:
                mreq = struct.pack(
                    "4sl",
                    socket.inet_aton(SSDP_MULTICAST_GROUP),
                    socket.INADDR_ANY,
                )
                sock.setsockopt(
                    socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
                )
            except OSError as mcast_err:
                logger.warning(
                    "Cannot join SSDP multicast group: %s", mcast_err
                )

            sock.setblocking(False)
            logger.info("SSDP listener active on %s:%d", SSDP_MULTICAST_GROUP, SSDP_PORT)

            while self._running:
                try:
                    data, addr = await asyncio.wait_for(
                        asyncio.get_event_loop().sock_recvfrom(
                            sock, SSDP_BUFFER_SIZE
                        ),
                        timeout=1.0,
                    )
                    message = data.decode("utf-8", errors="ignore")
                    await self._handle_ssdp_message(message, addr[0])
                except asyncio.TimeoutError:
                    await asyncio.sleep(0.5)
                    continue
                except asyncio.CancelledError:
                    break
                except OSError as exc:
                    logger.debug("SSDP socket error: %s", exc)
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    logger.debug("SSDP receive error: %s", exc)
                    await asyncio.sleep(0.1)

        except OSError as exc:
            logger.error("SSDP listener socket creation failed: %s", exc)
        except Exception as exc:
            logger.error("SSDP listener unexpected error: %s", exc)
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            logger.info("SSDP listener stopped")

    async def _handle_ssdp_message(self, message: str, source_ip: str) -> None:
        """
        Parse an SSDP NOTIFY or M-SEARCH response message.

        Extracts device information from the SSDP headers and invokes
        the appropriate callback.

        Args:
            message: Raw SSDP message string.
            source_ip: IP address of the device that sent the message.
        """
        if not message.strip():
            return

        lines = message.split("\r\n")
        if not lines:
            return

        # Parse headers into a dictionary
        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().upper()] = value.strip()

        # Determine message type
        first_line = lines[0].strip()
        is_notify = first_line.startswith("NOTIFY")
        is_response = first_line.startswith("HTTP/1.1 200 OK")

        if not (is_notify or is_response):
            return

        # Extract key fields
        usn = headers.get("USN", "")
        location = headers.get("LOCATION", "")
        st = headers.get("ST", headers.get("NT", ""))
        server = headers.get("SERVER", "")
        nts = headers.get("NTS", "")

        # Skip byebye notifications
        if "byebye" in nts.lower():
            device_id = usn if usn else f"ssdp_{source_ip}"
            self.on_state_change(
                {
                    "device_id": device_id,
                    "source_ip": source_ip,
                    "online": False,
                    "protocol": "ssdp",
                    "state": {"ssdp_headers": headers},
                }
            )
            return

        # Try to identify manufacturer
        manufacturer = self._identify_manufacturer(server, usn, st)

        # Try to identify device type
        device_type = self._identify_device_type(st, usn, server)

        # Build device ID
        device_id = usn if usn else f"{manufacturer}_{source_ip}"

        device_info: Dict[str, Any] = {
            "device_id": device_id,
            "source_ip": source_ip,
            "manufacturer": manufacturer,
            "device_type": device_type,
            "model": self._extract_model(server, usn),
            "online": True,
            "protocol": "ssdp",
            "location": location,
            "usn": usn,
            "st": st,
            "state": {
                "ip": source_ip,
                "location": location,
                "server": server,
                "ssdp_headers": headers,
            },
        }

        if is_notify:
            logger.debug(
                "SSDP NOTIFY from %s: %s (%s)",
                source_ip,
                manufacturer,
                device_type,
            )
            self.on_device_found(device_info)
        elif is_response:
            logger.debug(
                "SSDP response from %s: %s (%s)",
                source_ip,
                manufacturer,
                device_type,
            )
            self.on_device_found(device_info)

    # ─── mDNS Listener ──────────────────────────────────────────────────────

    async def _mdns_listener(self) -> None:
        """
        Listen for mDNS (multicast DNS) service announcements.

        Uses the zeroconf library to browse for known smart home service
        types on the local network. Falls back to a passive UDP listener
        if zeroconf is not available.
        """
        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener

            class HubServiceListener(ServiceListener):
                """Inner class implementing zeroconf ServiceListener interface."""

                def __init__(self, outer: "NetworkDiscoveryListener"):
                    self.outer = outer

                def add_service(
                    self, zc: Zeroconf, type_: str, name: str
                ) -> None:
                    """Called when a new service is discovered."""
                    info = zc.get_service_info(type_, name)
                    if info:
                        self._process_service(info, type_, name)

                def remove_service(
                    self, zc: Zeroconf, type_: str, name: str
                ) -> None:
                    """Called when a service is removed."""
                    device_id = f"mdns_{name}"
                    if self.outer._running:
                        self.outer.on_state_change(
                            {
                                "device_id": device_id,
                                "online": False,
                                "protocol": "mdns",
                            }
                        )

                def update_service(
                    self, zc: Zeroconf, type_: str, name: str
                ) -> None:
                    """Called when a service is updated."""
                    info = zc.get_service_info(type_, name)
                    if info:
                        self._process_service(info, type_, name)

                def _process_service(
                    self, info, type_: str, name: str
                ) -> None:
                    """Process a discovered service into a device info dict."""
                    ip = ""
                    if info.parsed_addresses():
                        ip = info.parsed_addresses()[0]

                    device_id = f"mdns_{name}"
                    manufacturer = self.outer._identify_manufacturer(name, type_, "")
                    device_type = self.outer._identify_device_type(type_, name, "")

                    device_info: Dict[str, Any] = {
                        "device_id": device_id,
                        "source_ip": ip,
                        "manufacturer": manufacturer,
                        "device_type": device_type,
                        "model": name.split(".")[0] if "." in name else name,
                        "online": True,
                        "protocol": "mdns",
                        "port": info.port,
                        "state": {
                            "ip": ip,
                            "port": info.port,
                            "server": info.server,
                            "properties": {
                                k.decode("utf-8", errors="ignore"): v.decode(
                                    "utf-8", errors="ignore"
                                )
                                if isinstance(v, bytes)
                                else str(v)
                                for k, v in (info.properties or {}).items()
                            },
                        },
                    }

                    if self.outer._running:
                        self.outer.on_device_found(device_info)

            # Services to browse for
            service_types = [
                "_hap._tcp.local.",      # HomeKit Accessory Protocol
                "_http._tcp.local.",     # HTTP services
                "_lutron._tcp.local.",   # Lutron Caseta
                "_ewelink._tcp.local.",  # Sonoff eWeLink
                "_googlecast._tcp.local.",  # Google Cast (Nest)
            ]

            zeroconf = Zeroconf()
            listener = HubServiceListener(self)

            browsers = [
                ServiceBrowser(zeroconf, service_type, listener)
                for service_type in service_types
            ]

            logger.info(
                "mDNS listener active — browsing %d service types",
                len(service_types),
            )

            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)

            # Cleanup
            for browser in browsers:
                browser.cancel()
            zeroconf.close()

        except ImportError:
            logger.warning(
                "zeroconf library not installed — mDNS discovery disabled. "
                "Install with: pip install zeroconf"
            )
        except Exception as exc:
            logger.error("mDNS listener error: %s", exc)
        finally:
            logger.info("mDNS listener stopped")

    # ─── UDP Broadcast Listener ─────────────────────────────────────────────

    async def _udp_broadcast_listener(self) -> None:
        """
        Listen for generic UDP broadcast announcements.

        Listens on manufacturer-specific broadcast ports for devices
        that announce themselves via UDP broadcasts (e.g., TP-Link Kasa
        on port 9999, LIFX on port 56700).
        """
        # Map of ports to manufacturer hints
        manufacturer_ports = {
            9999: "tp_link_kasa",
            56700: "lifx",
            80: "eoeeies",
            8081: "sonoff",
        }

        # Try to listen on each known port
        sockets: List[socket.socket] = []
        for port, manufacturer in manufacturer_ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                try:
                    sock.bind(("0.0.0.0", port))
                    sock.setblocking(False)
                    sockets.append(sock)
                    logger.info(
                        "UDP broadcast listener bound to port %d (%s)",
                        port,
                        manufacturer,
                    )
                except OSError as bind_err:
                    logger.debug(
                        "Cannot bind UDP port %d: %s", port, bind_err
                    )
                    sock.close()
            except Exception as exc:
                logger.debug("UDP socket creation error for port %d: %s", port, exc)

        if not sockets:
            logger.warning("No UDP broadcast ports could be bound")
            return

        logger.info(
            "UDP broadcast listener active on %d port(s)", len(sockets)
        )

        try:
            while self._running:
                for sock in sockets:
                    if not self._running:
                        break
                    try:
                        data, addr = await asyncio.wait_for(
                            asyncio.get_event_loop().sock_recvfrom(sock, 4096),
                            timeout=0.5,
                        )
                        port = sock.getsockname()[1]
                        manufacturer = manufacturer_ports.get(port, "unknown")
                        await self._handle_udp_broadcast(
                            data, addr[0], addr[1], port, manufacturer
                        )
                    except asyncio.TimeoutError:
                        await asyncio.sleep(0.2)
                        continue
                    except asyncio.CancelledError:
                        break
                    except Exception as exc:
                        logger.debug("UDP receive error: %s", exc)
                        await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("UDP broadcast listener error: %s", exc)
        finally:
            for sock in sockets:
                try:
                    sock.close()
                except Exception:
                    pass
            logger.info("UDP broadcast listener stopped")

    async def _handle_udp_broadcast(
        self,
        data: bytes,
        source_ip: str,
        source_port: int,
        local_port: int,
        manufacturer: str,
    ) -> None:
        """
        Handle a UDP broadcast message.

        Args:
            data: Raw bytes received.
            source_ip: Source IP address.
            source_port: Source port number.
            local_port: Local port the message was received on.
            manufacturer: Detected manufacturer hint.
        """
        # TP-Link Kasa devices send XOR-encrypted JSON
        if manufacturer == "tp_link_kasa":
            try:
                decrypted = self._kasa_xor_decrypt(data)
                import json

                parsed = json.loads(decrypted)
                system_info = parsed.get("system", {}).get("get_sysinfo", {})
                device_id = system_info.get("deviceId", f"kasa_{source_ip}")
                model = system_info.get("model", "unknown")
                device_type = (
                    "plug"
                    if "plug" in model.lower() or "hs" in model.lower()
                    else "light"
                    if "lb" in model.lower() or "kl" in model.lower()
                    else "unknown"
                )

                device_info: Dict[str, Any] = {
                    "device_id": device_id,
                    "source_ip": source_ip,
                    "manufacturer": "tp_link_kasa",
                    "device_type": device_type,
                    "model": model,
                    "online": True,
                    "protocol": "tcp",
                    "port": 9999,
                    "state": {
                        "ip": source_ip,
                        "port": 9999,
                        "relay_state": system_info.get("relay_state"),
                        "brightness": system_info.get("brightness"),
                        "rssi": system_info.get("rssi"),
                        "raw_info": system_info,
                    },
                }

                self.on_device_found(device_info)
            except Exception as exc:
                logger.debug(
                    "Failed to parse TP-Link Kasa broadcast from %s: %s",
                    source_ip,
                    exc,
                )
        else:
            # Generic UDP broadcast — log for unknown protocols
            logger.debug(
                "UDP broadcast from %s:%d on local port %d (%s): %d bytes",
                source_ip,
                source_port,
                local_port,
                manufacturer,
                len(data),
            )

    # ─── Helper Methods ─────────────────────────────────────────────────────

    @staticmethod
    def _identify_manufacturer(server: str, usn: str, st: str) -> str:
        """
        Identify the manufacturer from SSDP headers.

        Args:
            server: SERVER header value.
            usn: USN header value.
            st: ST/NT header value.

        Returns:
            Manufacturer key string.
        """
        combined = f"{server} {usn} {st}"
        for mfr, pattern in SSDP_MANUFACTURER_PATTERNS.items():
            if pattern.search(combined):
                return mfr
        return "unknown"

    @staticmethod
    def _identify_device_type(st: str, usn: str, server: str) -> str:
        """
        Identify the device type from SSDP headers.

        Args:
            st: ST/NT header value.
            usn: USN header value.
            server: SERVER header value.

        Returns:
            Device type string ("light", "plug", "camera", "thermostat", or "unknown").
        """
        combined = f"{st} {usn} {server}"
        for dtype, pattern in DEVICE_TYPE_PATTERNS.items():
            if pattern.search(combined):
                return dtype
        return "unknown"

    @staticmethod
    def _extract_model(server: str, usn: str) -> str:
        """Extract model information from SSDP headers."""
        # Try to find model info in SERVER header (e.g., "Linux/3.14 UPnP/1.0 IpBridge/1.50")
        if "/" in server:
            parts = server.split("/")
            if len(parts) >= 2:
                return parts[-1].strip()
        return "unknown"

    @staticmethod
    def _kasa_xor_decrypt(ciphertext: bytes) -> str:
        """
        Decrypt TP-Link Kasa XOR-encrypted payload.

        Kasa devices use a simple XOR cipher where the first byte is the
        key and each subsequent byte is XORed with the previous plaintext byte.

        Args:
            ciphertext: Raw encrypted bytes from a Kasa device.

        Returns:
            Decrypted JSON string.
        """
        if len(ciphertext) < 4:
            return "{}"

        # First 4 bytes are the big-endian length of the JSON payload
        key = ciphertext[0x00]
        plaintext = bytearray()
        prev = key

        for i in range(4, len(ciphertext)):
            decrypted = ciphertext[i] ^ prev
            plaintext.append(decrypted)
            prev = ciphertext[i]

        return plaintext.decode("utf-8", errors="ignore")
