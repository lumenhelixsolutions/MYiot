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
import time
import uuid
from typing import Awaitable, Callable, Dict, Any, Optional, List, Union

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
        on_device_found: Callable[
            [Dict[str, Any]], Union[None, Awaitable[None]]
        ],
        on_state_change: Callable[
            [Dict[str, Any]], Union[None, Awaitable[None]]
        ],
        on_event: Optional[
            Callable[[Dict[str, Any]], Union[None, Awaitable[None]]]
        ] = None,
    ):
        """
        Initialize the discovery listener.

        Args:
            on_device_found: Callback invoked when a new device is discovered.
                Receives a dictionary with device details.
            on_state_change: Callback invoked when a known device's state changes.
                Receives a dictionary with updated device details.
            on_event: Optional callback for scan progress / pending device updates.
        """
        self.on_device_found = on_device_found
        self.on_state_change = on_state_change
        self.on_event = on_event
        self._listeners: List[asyncio.Task] = []
        self._running = False
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._scan_state: Dict[str, Any] = {
            "active": False,
            "progress": 0,
            "message": "Idle",
            "protocols": [],
            "started_at": None,
            "completed_at": None,
        }
        self._scan_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _schedule_coroutine(self, coro: Awaitable[Any]) -> None:
        """Schedule work on the listener loop (safe from zeroconf threads)."""
        loop = self._loop
        if loop is None:
            logger.warning(
                "Cannot schedule discovery work — listener not started"
            )
            return
        try:
            if asyncio.get_running_loop() is loop:
                asyncio.create_task(coro)
                return
        except RuntimeError:
            pass
        asyncio.run_coroutine_threadsafe(coro, loop)

    async def _invoke_callback(
        self,
        callback: Callable[..., Union[None, Awaitable[None]]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        try:
            result = callback(*args, **kwargs)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.debug("Discovery callback failed: %s", exc)

    async def start(self) -> None:
        """Start all discovery listeners concurrently."""
        if self._running:
            logger.warning("Discovery listener already running")
            return

        self._running = True
        self._loop = asyncio.get_running_loop()
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
            await self._emit_state_change(
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
            await self._emit_device_found(device_info)
        elif is_response:
            logger.debug(
                "SSDP response from %s: %s (%s)",
                source_ip,
                manufacturer,
                device_type,
            )
            await self._emit_device_found(device_info)

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
                        self.outer._schedule_coroutine(
                            self.outer._emit_state_change(
                                {
                                    "device_id": device_id,
                                    "online": False,
                                    "protocol": "mdns",
                                }
                            )
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
                        self.outer._schedule_coroutine(
                            self.outer._emit_device_found(device_info)
                        )

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

                await self._emit_device_found(device_info)
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

    # ─── Scan API ───────────────────────────────────────────────────────────

    def get_scan_status(self) -> Dict[str, Any]:
        """Return current scan progress for REST/WS consumers."""
        return {
            **self._scan_state,
            "devices_found": len(self._pending),
        }

    def get_pending_devices(self) -> List[Dict[str, Any]]:
        """Return devices discovered but not yet registered on the hub."""
        return sorted(
            self._pending.values(),
            key=lambda d: d.get("discovered_at", 0),
            reverse=True,
        )

    def pop_pending_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Remove and return a pending device once registered."""
        return self._pending.pop(device_id, None)

    async def start_active_scan(self) -> Dict[str, Any]:
        """Kick off a global active scan across SSDP, mDNS, and UDP probes."""
        if self._scan_task and not self._scan_task.done():
            return self.get_scan_status()

        self._pending.clear()
        self._scan_state = {
            "active": True,
            "progress": 0,
            "message": "Initializing global scan...",
            "protocols": ["ssdp", "mdns", "udp"],
            "started_at": time.time(),
            "completed_at": None,
        }
        await self._emit_event({"type": "scan_progress", **self._scan_state})
        self._scan_task = asyncio.create_task(self._run_active_scan())
        return self.get_scan_status()

    async def stop_active_scan(self) -> Dict[str, Any]:
        """Stop an in-progress active scan."""
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        self._scan_state.update(
            {
                "active": False,
                "message": "Scan stopped",
                "completed_at": time.time(),
            }
        )
        await self._emit_event({"type": "scan_progress", **self._scan_state})
        return self.get_scan_status()

    async def _run_active_scan(self) -> None:
        """Execute phased network discovery with live progress updates."""
        phases = [
            (15, "Probing mDNS services..."),
            (35, "Broadcasting SSDP M-SEARCH..."),
            (55, "Scanning SSDP multicast..."),
            (70, "Listening for UDP device broadcasts..."),
            (85, "Classifying discovered hardware..."),
            (95, "Finalizing device fingerprints..."),
        ]
        try:
            await self._send_ssdp_msearch()
            for progress, message in phases:
                if not self._running:
                    break
                self._scan_state.update({"progress": progress, "message": message})
                await self._emit_event({"type": "scan_progress", **self._scan_state})
                await self._advance_pending_phases()
                await asyncio.sleep(1.2)

            await asyncio.sleep(2.0)
            await self._advance_pending_phases(finalize=True)
            count = len(self._pending)
            self._scan_state.update(
                {
                    "active": False,
                    "progress": 100,
                    "message": f"Found {count} device{'s' if count != 1 else ''}",
                    "completed_at": time.time(),
                }
            )
            await self._emit_event({"type": "scan_complete", **self._scan_state})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Active scan failed: %s", exc)
            self._scan_state.update(
                {
                    "active": False,
                    "message": f"Scan error: {exc}",
                    "completed_at": time.time(),
                }
            )
            await self._emit_event({"type": "scan_progress", **self._scan_state})
        finally:
            self._scan_task = None

    async def _send_ssdp_msearch(self) -> None:
        """Broadcast SSDP M-SEARCH requests for common smart-home service types."""
        search_targets = [
            "ssdp:all",
            "upnp:rootdevice",
            "urn:schemas-upnp-org:device:Basic:1",
            "urn:schemas-upnp-org:device:MediaServer:1",
        ]
        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            for st in search_targets:
                payload = (
                    "M-SEARCH * HTTP/1.1\r\n"
                    f"HOST: {SSDP_MULTICAST_GROUP}:{SSDP_PORT}\r\n"
                    'MAN: "ssdp:discover"\r\n'
                    "MX: 2\r\n"
                    f"ST: {st}\r\n"
                    "\r\n"
                ).encode("utf-8")
                sock.sendto(
                    payload,
                    (SSDP_MULTICAST_GROUP, SSDP_PORT),
                )
                await asyncio.sleep(0.15)
        except OSError as exc:
            logger.warning("SSDP M-SEARCH broadcast failed: %s", exc)
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    async def _advance_pending_phases(
        self, finalize: bool = False
    ) -> None:
        """Progress pending devices through probing -> complete phases."""
        phase_order = ["probing", "authenticating", "classifying", "complete"]
        for device in self._pending.values():
            current = device.get("scan_phase", "probing")
            if finalize:
                device["scan_phase"] = "complete"
            elif current in phase_order:
                idx = phase_order.index(current)
                if idx < len(phase_order) - 1:
                    device["scan_phase"] = phase_order[idx + 1]
            await self._emit_event(
                {
                    "type": "device_discovered",
                    "device": device,
                }
            )

    async def _emit_state_change(self, device_info: Dict[str, Any]) -> None:
        await self._invoke_callback(self.on_state_change, device_info)

    async def _emit_device_found(self, device_info: Dict[str, Any]) -> None:
        """Record a discovery hit, notify callbacks, and broadcast to clients."""
        pending = self._upsert_pending(device_info)
        await self._invoke_callback(self.on_device_found, device_info)
        await self._emit_event({"type": "device_discovered", "device": pending})

    def _upsert_pending(self, device_info: Dict[str, Any]) -> Dict[str, Any]:
        device_id = device_info.get("device_id") or device_info.get("usn") or str(
            uuid.uuid4()
        )
        ip = (
            device_info.get("source_ip")
            or device_info.get("state", {}).get("ip")
            or device_info.get("state", {}).get("ip_address")
            or ""
        )
        manufacturer = device_info.get("manufacturer", "unknown")
        device_type = device_info.get("device_type", "unknown")
        protocol = str(device_info.get("protocol", "ssdp")).upper()
        name = (
            device_info.get("state", {}).get("name")
            or device_info.get("model")
            or f"{manufacturer} {device_type}".strip()
        )

        existing = self._pending.get(device_id)
        if existing:
            existing.update(
                {
                    "ip_address": ip or existing.get("ip_address", ""),
                    "signal_strength": max(
                        existing.get("signal_strength", 0),
                        device_info.get("state", {}).get("rssi", 72),
                    ),
                    "scan_phase": "classifying",
                    "last_seen": time.time(),
                }
            )
            return existing

        pending = {
            "id": device_id,
            "device_id": device_id,
            "name": name,
            "manufacturer": manufacturer,
            "model": device_info.get("model", "unknown"),
            "device_type": device_type,
            "ip_address": ip,
            "protocol": protocol,
            "mac_address": device_info.get("mac_address", ""),
            "firmware": device_info.get("firmware", "unknown"),
            "signal_strength": device_info.get("state", {}).get("rssi", 68),
            "scan_phase": "probing",
            "discovered_at": time.time(),
            "last_seen": time.time(),
            "location": device_info.get("location", ""),
            "usn": device_info.get("usn", ""),
        }
        self._pending[device_id] = pending
        return pending

    async def _emit_event(self, payload: Dict[str, Any]) -> None:
        if not self.on_event:
            return
        await self._invoke_callback(self.on_event, payload)

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
