# Smart Home Universal Hub — Backend Specification

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React SPA)                            │
│  Dashboard │ Device Grid │ Control Panel │ Settings │ Activity Log      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                    REST API            WebSocket /ws
              (HTTP/CRUD/Auth)      (Real-time state push)
                         │                     │
└────────────────────────┴─────────────────────┴──────────────────────────┘
│                         FASTAPI APPLICATION LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Device Mgmt  │  │ Discovery    │  │ Command      │  │ Auth        │ │
│  │ API Router   │  │ API Router   │  │ API Router   │  │ API Router  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
│         └─────────────────┬───────────────────┘                 │        │
│                           ▼                                    │        │
│  ┌─────────────────────────────────────────────────────────┐   │        │
│  │              UNIVERSAL DEVICE ENGINE                     │   │        │
│  │  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │   │        │
│  │  │StateRegistry│ │Actuation     │ │Network Discovery │  │   │        │
│  │  │(in-memory)  │ │Dispatcher    │ │Listener (mDNS/   │  │   │        │
│  │  │             │ │(HTTP/TCP)    │ │ SSDP/UDP)        │  │   │        │
│  │  └──────┬──────┘ └──────┬───────┘ └────────┬─────────┘  │   │        │
│  │         └─────────────────┼──────────────────┘            │   │        │
│  │                           ▼                               │   │        │
│  │  ┌─────────────────────────────────────────────────────┐  │   │        │
│  │  │           PLUGIN DRIVER SYSTEM                       │  │   │        │
│  │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │  │   │        │
│  │  │  │Hue     │ │Kasa    │ │Nest    │ │Generic │  ...  │  │   │        │
│  │  │  │Plugin  │ │Plugin  │ │Plugin  │ │REST    │       │  │   │        │
│  │  │  │        │ │        │ │        │ │Plugin  │       │  │   │        │
│  │  │  └────────┘ └────────┘ └────────┘ └────────┘       │  │   │        │
│  │  └─────────────────────────────────────────────────────┘  │   │        │
│  └───────────────────────────────────────────────────────────┘   │        │
│                                                                  │        │
│  ┌───────────────────────────────────────────────────────────────┘        │
│  │                    AUTH & DATA LAYER                                     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  │ Credential   │  │ Manufacturer │  │ SQLite       │                  │
│  │  │ Manager      │  │ Map Registry │  │ Persistence  │                  │
│  │  │ (token store)│  │ (MANUFACT_   │  │ (device      │                  │
│  │  │              │  │  URER_MAPS)  │  │  configs)    │                  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │
│  └─────────────────────────────────────────────────────────────────────────┘
└────────────────────────────────────────────────────────────────────────────┘
```

## 2. Module Specification

### 2.1 Base Driver Interface (`core/base_driver.py`)

Every manufacturer plugin must inherit from `BaseDriver`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel

class DeviceState(BaseModel):
    """Standardized device state model."""
    device_id: str
    manufacturer: str
    model: str
    device_type: str  # "plug" | "light" | "thermostat" | "camera"
    online: bool
    state: Dict[str, Any]
    last_updated: float  # Unix timestamp

class BaseDriver(ABC):
    """Abstract base class for all manufacturer plugins."""

    def __init__(self, device_config: Dict[str, Any]):
        self.config = device_config
        self.device_id = device_config["device_id"]
        self.manufacturer = device_config["manufacturer"]
        self.model = device_config.get("model", "unknown")
        self.device_type = device_config["device_type"]
        self._session = None
        self._connected = False

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Handle authentication — local network or cloud API tokens."""
        pass

    @abstractmethod
    async def get_state(self) -> DeviceState:
        """Poll device and return standardized state dictionary."""
        pass

    @abstractmethod
    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Receive standard payload, translate to manufacturer-specific command."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Safely close sessions/sockets."""
        pass

    # Optional: override for cameras
    async def capture_snapshot(self) -> Optional[bytes]:
        """Request single static frame (cameras only)."""
        return None

    # Optional: override for cameras
    async def get_stream_url(self) -> Optional[str]:
        """Return RTSP/WebRTC stream URI (cameras only)."""
        return None
```

### 2.2 Standardized Payloads (`core/payloads.py`)

```python
from typing import Union, Tuple, Optional
from pydantic import BaseModel, Field, validator

class SmartPlugPayload(BaseModel):
    """Payload schema for smart plugs."""
    power: bool

class SmartLightPayload(BaseModel):
    """Payload schema for smart lights."""
    power: Optional[bool] = None
    brightness: Optional[int] = Field(None, ge=0, le=100)
    color: Optional[Union[str, Tuple[int, int, int]]] = None

class ThermostatPayload(BaseModel):
    """Payload schema for thermostats."""
    mode: Optional[str] = Field(None, regex="^(heat|cool|auto|off)$")
    target_temp: Optional[float] = None

class CameraPayload(BaseModel):
    """Payload schema for cameras."""
    power: Optional[bool] = None

# Union type for all payloads
DevicePayload = Union[SmartPlugPayload, SmartLightPayload, ThermostatPayload, CameraPayload]
```

### 2.3 State Registry (`core/state_registry.py`)

```python
import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict

class StateRegistry:
    """
    Lightweight, centralized in-memory state dictionary.
    Holds current status of all discovered devices.
    Updated only from incoming broadcast data (event-driven).
    """

    def __init__(self):
        self._state: Dict[str, DeviceState] = {}
        self._listeners: List[Callable[[str, DeviceState], None]] = []
        self._lock = asyncio.Lock()

    async def update(self, device_id: str, state: DeviceState) -> None:
        """Update device state and notify listeners."""
        async with self._lock:
            self._state[device_id] = state
        await self._notify(device_id, state)

    async def get(self, device_id: str) -> Optional[DeviceState]:
        """Get current state for a device."""
        return self._state.get(device_id)

    async def get_all(self, device_type: Optional[str] = None) -> List[DeviceState]:
        """Get all devices, optionally filtered by type."""
        states = list(self._state.values())
        if device_type:
            states = [s for s in states if s.device_type == device_type]
        return states

    async def remove(self, device_id: str) -> None:
        """Remove a device from the registry."""
        async with self._lock:
            self._state.pop(device_id, None)

    def subscribe(self, callback: Callable[[str, DeviceState], None]) -> None:
        """Subscribe to state change events."""
        self._listeners.append(callback)

    async def _notify(self, device_id: str, state: DeviceState) -> None:
        """Notify all listeners of state change."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(device_id, state)
                else:
                    listener(device_id, state)
            except Exception:
                pass  # Don't let listener errors crash the registry
```

### 2.4 Manufacturer Maps (`core/manufacturer_maps.py`)

```python
MANUFACTURER_MAPS = {
    "philips_hue": {
        "protocol": "rest",
        "base_url_template": "http://{ip}/api/{username}",
        "auth_type": "bridge_token",
        "device_types": ["light"],
        "endpoints": {
            "get_lights": "/lights",
            "set_light": "/lights/{id}/state",
        },
        "payload_map": {
            "light": {
                "power": "on",
                "brightness": "bri",
                "color": "xy",
            }
        },
        "discovery": {
            "method": "upnp_ssdp",
            "ssdp_st": "urn:schemas-upnp-org:device:basic:1",
            "ssdp_mx": 3,
        }
    },
    "tp_link_kasa": {
        "protocol": "tcp",
        "port": 9999,
        "auth_type": "none",
        "device_types": ["plug", "light"],
        "payload_map": {
            "plug": {
                "system": {"set_relay_state": {"state": "power"}}
            },
            "light": {
                "smartlife.iot.dimmer": {"set_brightness": {"brightness": "brightness"}},
            }
        },
        "discovery": {
            "method": "udp_broadcast",
            "port": 9999,
            "broadcast_addr": "255.255.255.255",
        }
    },
    "nest": {
        "protocol": "rest",
        "base_url": "https://smartdevicemanagement.googleapis.com/v1",
        "auth_type": "oauth2",
        "device_types": ["thermostat", "camera"],
        "endpoints": {
            "devices": "/enterprises/{project_id}/devices",
            "execute": "/enterprises/{project_id}/devices/{device_id}:executeCommand",
        },
        "payload_map": {
            "thermostat": {
                "mode": "thermostatMode",
                "target_temp": "heatCelsius",
            },
            "camera": {
                "power": "cameraEnabled",
            }
        },
        "discovery": {
            "method": "oauth_cloud",
        }
    },
    "wemo": {
        "protocol": "soap",
        "port": 49153,
        "auth_type": "none",
        "device_types": ["plug"],
        "discovery": {
            "method": "upnp_ssdp",
            "ssdp_st": "urn:Belkin:device:controllee:1",
        }
    },
    "lifx": {
        "protocol": "rest",
        "base_url_template": "https://api.lifx.com/v1",
        "auth_type": "bearer_token",
        "device_types": ["light"],
        "endpoints": {
            "lights": "/lights/all",
            "set_state": "/lights/{selector}/state",
        },
        "discovery": {
            "method": "lan",
            "port": 56700,
        }
    },
    "govee": {
        "protocol": "rest",
        "base_url": "https://developer-api.govee.com/v1",
        "auth_type": "api_key",
        "device_types": ["light"],
        "discovery": {
            "method": "cloud_api",
        }
    },
    "wyze": {
        "protocol": "rest",
        "base_url": "https://api.wyzecam.com",
        "auth_type": "user_password",
        "device_types": ["light", "camera", "plug"],
        "discovery": {
            "method": "cloud_api",
        }
    },
    "ikea_tradfri": {
        "protocol": "coap",
        "port": 5684,
        "auth_type": "psk",
        "device_types": ["light", "plug"],
        "discovery": {
            "method": "coap_dtls",
            "port": 5684,
        }
    },
    "ecobee": {
        "protocol": "rest",
        "base_url": "https://api.ecobee.com",
        "auth_type": "oauth2_pin",
        "device_types": ["thermostat"],
        "discovery": {
            "method": "oauth_cloud",
        }
    },
    "honeywell": {
        "protocol": "rest",
        "base_url": "https://api.honeywell.com/v2",
        "auth_type": "oauth2",
        "device_types": ["thermostat"],
        "discovery": {
            "method": "oauth_cloud",
        }
    },
    "emerson_sensi": {
        "protocol": "rest",
        "base_url": "https://api.sensi.com",
        "auth_type": "oauth2",
        "device_types": ["thermostat"],
        "discovery": {
            "method": "oauth_cloud",
        }
    },
    "mysa": {
        "protocol": "rest",
        "base_url": "https://api.mysa.energy/v1",
        "auth_type": "bearer_token",
        "device_types": ["thermostat"],
        "discovery": {
            "method": "cloud_api",
        }
    },
    "blink": {
        "protocol": "rest",
        "base_url": "https://rest-prod.immedia-semi.com",
        "auth_type": "user_password",
        "device_types": ["camera"],
        "discovery": {
            "method": "cloud_api",
        }
    },
    "ring": {
        "protocol": "rest",
        "base_url": "https://api.ring.com/clients_api",
        "auth_type": "oauth2",
        "device_types": ["camera"],
        "discovery": {
            "method": "oauth_cloud",
        }
    },
    "eoeeies": {
        "protocol": "rest",
        "base_url_template": "http://{ip}/api/v1",
        "auth_type": "basic_auth",
        "device_types": ["camera"],
        "endpoints": {
            "status": "/status",
            "snapshot": "/snapshot",
            "stream": "/stream",
            "control": "/control",
        },
        "payload_map": {
            "camera": {
                "power": "enabled",
            }
        },
        "discovery": {
            "method": "onvif",
            "port": 80,
        }
    },
    "sonoff": {
        "protocol": "rest",
        "base_url_template": "http://{ip}:8081/zeroconf",
        "auth_type": "bearer_token",
        "device_types": ["plug"],
        "discovery": {
            "method": "mDNS",
            "service": "_ewelink._tcp.local",
        }
    },
    "meross": {
        "protocol": "mqtt",
        "base_url": "mqtt.meross.com",
        "auth_type": "user_password",
        "device_types": ["plug"],
        "discovery": {
            "method": "cloud_api",
        }
    },
    "lutron_caseta": {
        "protocol": "leap",
        "port": 8081,
        "auth_type": "certificate",
        "device_types": ["plug", "light"],
        "discovery": {
            "method": "mDNS",
            "service": "_lutron._tcp.local",
        }
    },
}
```

### 2.5 Network Discovery Listener (`discovery/listener.py`)

```python
import asyncio
import socket
import struct
from typing import Callable, Dict, Any, Optional

class NetworkDiscoveryListener:
    """
    UDP, mDNS, and SSDP listeners for device discovery broadcasts.
    Catches real-time state changes without active polling.
    """

    def __init__(self, on_device_found: Callable[[Dict[str, Any]], None],
                 on_state_change: Callable[[Dict[str, Any]], None]):
        self.on_device_found = on_device_found
        self.on_state_change = on_state_change
        self._listeners: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start all discovery listeners."""
        self._running = True
        self._listeners = [
            asyncio.create_task(self._ssdp_listener()),
            asyncio.create_task(self._mdns_listener()),
            asyncio.create_task(self._udp_broadcast_listener()),
        ]

    async def stop(self) -> None:
        """Stop all listeners."""
        self._running = False
        for task in self._listeners:
            task.cancel()
        self._listeners.clear()

    async def _ssdp_listener(self) -> None:
        """Listen for SSDP (Simple Service Discovery Protocol) broadcasts."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", 1900))

            # Join multicast group
            mreq = struct.pack("4sl", socket.inet_aton("239.255.255.250"), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setblocking(False)

            while self._running:
                try:
                    data, addr = await asyncio.get_event_loop().sock_recvfrom(sock, 1024)
                    await self._handle_ssdp_message(data.decode('utf-8', errors='ignore'), addr[0])
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(0.1)
        except Exception:
            pass

    async def _mdns_listener(self) -> None:
        """Listen for mDNS ( multicast DNS) service announcements."""
        # Implementation using zeroconf library
        pass

    async def _udp_broadcast_listener(self) -> None:
        """Listen for UDP broadcast announcements (e.g., TP-Link Kasa)."""
        pass

    async def _handle_ssdp_message(self, message: str, source_ip: str) -> None:
        """Parse SSDP NOTIFY or M-SEARCH response."""
        pass
```

### 2.6 Actuation Dispatcher (`core/dispatcher.py`)

```python
import asyncio
import aiohttp
from typing import Dict, Any, Optional, Callable

class ActuationDispatcher:
    """
    Single dispatch_command function for outgoing HTTP/REST and TCP payload execution.
    Translates standardized inputs into hardware-specific payloads.
    """

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def dispatch_command(self, device_config: Dict[str, Any],
                                command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command on a device.
        Returns: {"success": bool, "response": Any, "error": Optional[str]}
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
            else:
                return {"success": False, "error": f"Unsupported protocol: {protocol}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _dispatch_rest(self, config: Dict[str, Any],
                              command: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch via HTTP/REST."""
        session = await self._get_session()
        url = config["url"]
        method = command.get("method", "POST")
        headers = config.get("headers", {})
        payload = command.get("payload", {})

        async with session.request(method, url, headers=headers, json=payload) as resp:
            return {
                "success": 200 <= resp.status < 300,
                "status": resp.status,
                "response": await resp.json() if resp.content_type == 'application/json' else await resp.text()
            }

    async def _dispatch_tcp(self, config: Dict[str, Any],
                             command: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch via raw TCP socket."""
        host = config["ip"]
        port = config["port"]
        payload = command.get("payload", b"")

        if isinstance(payload, dict):
            payload = json.dumps(payload).encode()

        reader, writer = await asyncio.open_connection(host, port)
        try:
            writer.write(payload)
            await writer.drain()
            data = await reader.read(4096)
            return {"success": True, "response": data.decode()}
        finally:
            writer.close()
            await writer.wait_closed()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
```

### 2.7 Authentication Manager (`auth/manager.py`)

```python
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet

class AuthenticationManager:
    """
    Token and credential storage module.
    Handles local network authentication handshakes.
    Securely stores credentials with encryption.
    """

    def __init__(self, storage_path: str = "./data/credentials.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._get_or_create_key()
        self._cipher = Fernet(self._key)
        self._credentials: Dict[str, Any] = {}
        self._load()

    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key."""
        key_path = self.storage_path.parent / ".key"
        if key_path.exists():
            return key_path.read_bytes()
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        return key

    def _load(self) -> None:
        """Load encrypted credentials from disk."""
        if self.storage_path.exists():
            encrypted = self.storage_path.read_bytes()
            try:
                decrypted = self._cipher.decrypt(encrypted)
                self._credentials = json.loads(decrypted)
            except Exception:
                self._credentials = {}

    def _save(self) -> None:
        """Save encrypted credentials to disk."""
        encrypted = self._cipher.encrypt(json.dumps(self._credentials).encode())
        self.storage_path.write_bytes(encrypted)

    def store(self, manufacturer: str, credentials: Dict[str, Any]) -> None:
        """Store credentials for a manufacturer."""
        self._credentials[manufacturer] = credentials
        self._save()

    def get(self, manufacturer: str) -> Optional[Dict[str, Any]]:
        """Retrieve credentials for a manufacturer."""
        return self._credentials.get(manufacturer)

    def delete(self, manufacturer: str) -> None:
        """Delete credentials for a manufacturer."""
        self._credentials.pop(manufacturer, None)
        self._save()

    async def authenticate_hue_bridge(self, ip: str) -> Optional[str]:
        """Special handler for Philips Hue bridge token creation."""
        pass
```

### 2.8 Plugin Loader (`core/plugin_loader.py`)

```python
import importlib
import pkgutil
from typing import Type, Dict, Any
from core.base_driver import BaseDriver

class PluginLoader:
    """Discovers and loads manufacturer plugin modules."""

    def __init__(self, plugin_package: str = "plugins"):
        self.plugin_package = plugin_package
        self._plugins: Dict[str, Type[BaseDriver]] = {}

    def discover(self) -> Dict[str, Type[BaseDriver]]:
        """Discover all available plugins."""
        try:
            package = importlib.import_module(self.plugin_package)
            for _, name, ispkg in pkgutil.iter_modules(package.__path__):
                if not ispkg and not name.startswith("_"):
                    try:
                        module = importlib.import_module(f"{self.plugin_package}.{name}")
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (isinstance(attr, type) and
                                issubclass(attr, BaseDriver) and
                                attr is not BaseDriver):
                                self._plugins[name] = attr
                    except Exception:
                        continue
        except ImportError:
            pass
        return self._plugins

    def get_plugin(self, name: str) -> Optional[Type[BaseDriver]]:
        """Get a plugin class by name."""
        return self._plugins.get(name)
```

### 2.9 FastAPI Application (`api/main.py`)

```python
from fastapi import FastAPI, WebSocket, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.registry = StateRegistry()
    app.state.discovery = NetworkDiscoveryListener(
        on_device_found=lambda d: asyncio.create_task(handle_discovery(d, app)),
        on_state_change=lambda d: asyncio.create_task(handle_state_change(d, app))
    )
    app.state.dispatcher = ActuationDispatcher()
    app.state.auth_manager = AuthenticationManager()
    app.state.plugin_loader = PluginLoader()
    app.state.plugin_loader.discover()

    await app.state.discovery.start()
    yield
    # Shutdown
    await app.state.discovery.stop()
    await app.state.dispatcher.close()

app = FastAPI(title="Smart Home Universal Hub", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── REST API Routes ──────────────────────────────────────────────────────

@app.get("/api/devices")
async def list_devices(device_type: Optional[str] = None, request=None):
    """List all discovered devices with optional type filter."""
    registry = request.app.state.registry
    return await registry.get_all(device_type)

@app.get("/api/devices/{device_id}")
async def get_device(device_id: str, request=None):
    """Get state for a specific device."""
    registry = request.app.state.registry
    state = await registry.get(device_id)
    if not state:
        raise HTTPException(status_code=404, detail="Device not found")
    return state

@app.post("/api/devices/{device_id}/command")
async def send_command(device_id: str, payload: Dict[str, Any], request=None):
    """Send a command to a device."""
    registry = request.app.state.registry
    dispatcher = request.app.state.dispatcher

    device = await registry.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    result = await dispatcher.dispatch_command(device.__dict__, payload)
    return result

@app.post("/api/devices/manual")
async def add_manual_device(config: Dict[str, Any], request=None):
    """Manually add a device by IP with custom manufacturer map."""
    registry = request.app.state.registry
    # Validate and add device
    device_state = DeviceState(
        device_id=config["device_id"],
        manufacturer=config["manufacturer"],
        model=config.get("model", "unknown"),
        device_type=config["device_type"],
        online=True,
        state={},
        last_updated=time.time()
    )
    await registry.update(config["device_id"], device_state)
    return {"success": True, "device_id": config["device_id"]}

@app.get("/api/manufacturers")
async def list_manufacturers():
    """List all supported manufacturers with their configurations."""
    return MANUFACTURER_MAPS

@app.post("/api/auth/{manufacturer}")
async def store_credentials(manufacturer: str, credentials: Dict[str, Any], request=None):
    """Store authentication credentials for a manufacturer."""
    auth = request.app.state.auth_manager
    auth.store(manufacturer, credentials)
    return {"success": True}

@app.get("/api/streams/{device_id}")
async def get_stream_uri(device_id: str, request=None):
    """Get RTSP/WebRTC stream URI for a camera device."""
    registry = request.app.state.registry
    device = await registry.get(device_id)
    if not device or device.device_type != "camera":
        raise HTTPException(status_code=404, detail="Camera not found")
    # Retrieve stream URL from manufacturer map or device
    return {"stream_url": device.state.get("stream_url")}

# ─── WebSocket Endpoint ───────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time state updates via WebSocket."""
    await websocket.accept()
    registry = websocket.app.state.registry

    async def on_state_change(device_id: str, state: DeviceState):
        await websocket.send_json({
            "type": "state_change",
            "device_id": device_id,
            "state": state.dict()
        })

    registry.subscribe(on_state_change)

    try:
        while True:
            message = await websocket.receive_json()
            # Handle incoming messages (commands, etc.)
            if message.get("action") == "command":
                device_id = message["device_id"]
                payload = message["payload"]
                # Execute command
    except Exception:
        pass
    finally:
        # Unsubscribe
        pass
```

## 3. Data Models

### 3.1 Device Configuration (SQLite)

```python
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class DeviceConfig(Base):
    __tablename__ = "devices"

    device_id = Column(String, primary_key=True)
    manufacturer = Column(String, nullable=False)
    model = Column(String)
    device_type = Column(String, nullable=False)
    ip_address = Column(String)
    port = Column(Integer)
    protocol = Column(String)
    auth_type = Column(String)
    credentials_key = Column(String)  # Reference to auth manager
    custom_map = Column(JSON)  # Custom manufacturer map override
    room = Column(String)
    name = Column(String)
    enabled = Column(Boolean, default=True)
```

### 3.2 Event Log

```python
class EventLog(Base):
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False)
    event_type = Column(String, nullable=False)  # "discovery" | "state_change" | "command" | "error"
    device_id = Column(String)
    manufacturer = Column(String)
    details = Column(JSON)
```

## 4. Project Structure

```
hub/
├── main.py                 # FastAPI app entry point
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build
├── README.md               # Documentation
├── api/
│   ├── __init__.py
│   ├── routes.py            # REST API route handlers
│   └── websocket.py         # WebSocket handlers
├── core/
│   ├── __init__.py
│   ├── base_driver.py       # Abstract base driver class
│   ├── payloads.py          # Standardized payload schemas
│   ├── state_registry.py    # In-memory state registry
│   ├── manufacturer_maps.py # Declarative manufacturer configs
│   ├── dispatcher.py        # Actuation dispatcher
│   └── plugin_loader.py     # Plugin discovery & loading
├── plugins/
│   ├── __init__.py
│   ├── philips_hue.py
│   ├── tp_link_kasa.py
│   ├── nest.py
│   ├── wemo.py
│   ├── lifx.py
│   ├── govee.py
│   ├── wyze.py
│   ├── ikea_tradfri.py
│   ├── ecobee.py
│   ├── honeywell.py
│   ├── emerson_sensi.py
│   ├── mysa.py
│   ├── blink.py
│   ├── ring.py
│   ├── eoeeies.py
│   ├── sonoff.py
│   ├── meross.py
│   ├── lutron_caseta.py
│   └── simulator.py         # Test plugin with mock devices
├── discovery/
│   ├── __init__.py
│   ├── listener.py          # Network discovery listeners
│   ├── ssdp.py              # SSDP protocol implementation
│   ├── mdns.py              # mDNS protocol implementation
│   └── parsers.py           # Discovery message parsers
├── auth/
│   ├── __init__.py
│   └── manager.py           # Credential storage & auth handlers
├── models/
│   ├── __init__.py
│   └── database.py          # SQLAlchemy models
└── data/                    # Runtime data (gitignored)
    └── .gitkeep
```

## 5. API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/devices` | List all devices (optional `?device_type=` filter) |
| GET | `/api/devices/{id}` | Get specific device state |
| POST | `/api/devices/{id}/command` | Send command to device |
| POST | `/api/devices/manual` | Manually add a device |
| DELETE | `/api/devices/{id}` | Remove a device |
| GET | `/api/manufacturers` | List supported manufacturers |
| POST | `/api/auth/{mfr}` | Store credentials for manufacturer |
| GET | `/api/streams/{id}` | Get camera stream URI |
| GET | `/api/logs` | Get event log (paginated) |
| WS | `/ws` | WebSocket for real-time updates |

## 6. Dependencies

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
aiohttp>=3.9.0
python-multipart>=0.0.6
websockets>=12.0
cryptography>=41.0.0
zeroconf>=0.130.0
```
