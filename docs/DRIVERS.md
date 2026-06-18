# MYiot Device Driver Development Guide

> **MYiot** — Universal Smart Home Hub
> Learn how to extend MYiot with support for new devices and protocols.
>
> **Brand Colors:** `#081021` (Deep Space Slate) | `#6366F1` (Electric Indigo) | `#06B6D4` (Cyan Glow) | `#F59E0B` (Warm Amber)

---

## Table of Contents

- [Overview](#overview)
- [Base Driver Interface](#base-driver-interface)
- [How to Add a New Manufacturer](#how-to-add-a-new-manufacturer)
- [Protocol Implementations](#protocol-implementations)
- [Driver Testing Guide](#driver-testing-guide)
- [Driver Registration](#driver-registration)
- [Reference: Existing Drivers](#reference-existing-drivers)

---

## Overview

MYiot's driver architecture is designed to be **extensible, testable, and protocol-agnostic**. The driver layer sits between the core application and physical devices, translating between MYiot's unified device model and protocol-specific messages.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     MYiot Core Application                       │
│                                                                  │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Device API  │  │ Automation  │  │    State Manager    │   │
│   │   Router    │  │   Engine    │  │                     │   │
│   └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │
│          │                │                     │               │
│          └────────────────┼─────────────────────┘               │
│                           │                                     │
│                   ┌───────▼────────┐                            │
│                   │  Device Service │                            │
│                   │   (Unified)     │                            │
│                   └───────┬────────┘                            │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Driver Layer                                │
│                                                                  │
│   ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ │
│   │   Zigbee   │ │   Z-Wave   │ │    WiFi    │ │    BLE     │ │
│   │   Driver   │ │   Driver   │ │   Driver   │ │   Driver   │ │
│   └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ │
│         │              │              │              │         │
│    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐   │
│    │Zigbee2  │    │Z-Wave   │    │  MQTT   │    │  BLE    │   │
│    │  MQTT   │    │   JS    │    │ Generic │    │ Adapter │   │
│    └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘   │
└─────────┼──────────────┼──────────────┼──────────────┼─────────┘
          │              │              │              │
     ┌────┴────┐    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
     │ Zigbee  │    │ Z-Wave  │    │  WiFi   │    │  BLE    │
     │ Devices │    │ Devices │    │ Devices │    │ Devices │
     └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

---

## Base Driver Interface

All device drivers must implement the `BaseDriver` abstract class:

```python
# app/drivers/base.py
"""
MYiot Device Driver Base Interface

All protocol drivers must inherit from BaseDriver and implement
the required abstract methods. This ensures a consistent API
across all device protocols.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


class ProtocolType(str, Enum):
    """Supported device communication protocols."""
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    WIFI = "wifi"
    BLE = "ble"
    MQTT = "mqtt"
    THREAD = "thread"
    MATTER = "matter"


class DeviceCapability(str, Enum):
    """Standardized device capabilities across all protocols."""
    # Power / Light
    ON_OFF = "on_off"
    DIMMER = "dimmer"
    COLOR = "color"           # RGB
    COLOR_TEMP = "color_temp" # White temperature (K)
    
    # Climate
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    THERMOSTAT = "thermostat"
    FAN = "fan"
    
    # Security / Sensors
    MOTION = "motion"
    CONTACT = "contact"
    VIBRATION = "vibration"
    SMOKE = "smoke"
    CO = "co"
    WATER_LEAK = "water_leak"
    
    # Access
    LOCK = "lock"
    COVER = "cover"           # Blinds, curtains, garage doors
    
    # Media
    CAMERA = "camera"
    SPEAKER = "speaker"
    
    # Power monitoring
    POWER = "power"
    CURRENT = "current"
    VOLTAGE = "voltage"
    ENERGY = "energy"


@dataclass
class DeviceInfo:
    """Standardized device information returned by discovery."""
    id: str                      # Unique device identifier
    name: str                    # Human-readable name
    manufacturer: str            # Device manufacturer
    model: str                   # Model number/name
    protocol: ProtocolType       # Communication protocol
    type: str                    # Device type (light, sensor, etc.)
    capabilities: list[str] = field(default_factory=list)
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    ieee_address: Optional[str] = None  # MAC/EUI-64
    battery_percent: Optional[int] = None
    signal_strength: Optional[int] = None  # RSSI in dBm
    room_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceState:
    """Standardized device state representation."""
    device_id: str
    state: dict[str, Any] = field(default_factory=dict)
    available: bool = True
    last_updated: datetime = field(default_factory=datetime.utcnow)


class BaseDriver(ABC):
    """
    Abstract base class for all device protocol drivers.
    
    Implementations must handle:
    - Protocol-specific initialization and connection
    - Device discovery and enumeration
    - State updates (read and write)
    - Message handling from the message bus
    - Graceful shutdown
    
    Example:
        class PhilipsHueDriver(BaseDriver):
            protocol = ProtocolType.ZIGBEE
            capabilities = {DeviceCapability.ON_OFF, DeviceCapability.DIMMER}
            
            async def initialize(self) -> None:
                # Connect to Hue Bridge
                pass
    """
    
    # Protocol identifier — must be set by subclass
    protocol: ProtocolType
    
    # Capabilities this driver supports
    capabilities: set[DeviceCapability]
    
    # Human-readable driver name
    name: str = "base"
    
    # Driver version (semver)
    version: str = "0.0.0"
    
    # Whether the driver is currently initialized
    _initialized: bool = False
    
    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """
        Initialize the driver with configuration.
        
        This method should:
        1. Validate configuration
        2. Establish connection to the protocol gateway
        3. Subscribe to relevant MQTT topics
        4. Set up any required background tasks
        
        Args:
            config: Driver-specific configuration dictionary
            
        Raises:
            DriverConfigError: If configuration is invalid
            DriverConnectionError: If connection fails
        """
        ...
    
    @abstractmethod
    async def discover(self, timeout: int = 30) -> list[DeviceInfo]:
        """
        Discover available devices on this protocol.
        
        Args:
            timeout: Maximum time to wait for discovery (seconds)
            
        Returns:
            List of discovered device information
        """
        ...
    
    @abstractmethod
    async def set_state(self, device_id: str, state: dict[str, Any]) -> DeviceState:
        """
        Send a state update to a device.
        
        Args:
            device_id: Target device identifier
            state: New state values to apply
            
        Returns:
            Updated device state after applying changes
            
        Raises:
            DeviceNotFound: If device doesn't exist
            DeviceOffline: If device is not reachable
            InvalidStateError: If state values are invalid
        """
        ...
    
    @abstractmethod
    async def get_state(self, device_id: str) -> DeviceState:
        """
        Read the current state of a device.
        
        Args:
            device_id: Target device identifier
            
        Returns:
            Current device state
        """
        ...
    
    @abstractmethod
    async def handle_message(self, topic: str, payload: dict[str, Any]) -> None:
        """
        Handle an incoming MQTT message for this protocol.
        
        The driver should parse protocol-specific messages and
        emit standardized events to the MYiot event bus.
        
        Args:
            topic: MQTT topic
            payload: Parsed JSON payload
        """
        ...
    
    async def shutdown(self) -> None:
        """
        Clean up resources and disconnect gracefully.
        
        Override this method to perform protocol-specific cleanup.
        Default implementation is a no-op.
        """
        self._initialized = False
    
    def is_initialized(self) -> bool:
        """Check if the driver has been initialized."""
        return self._initialized
    
    def supports_capability(self, capability: DeviceCapability) -> bool:
        """Check if this driver supports a specific capability."""
        return capability in self.capabilities


class DriverError(Exception):
    """Base exception for driver-related errors."""
    pass


class DriverConfigError(DriverError):
    """Raised when driver configuration is invalid."""
    pass


class DriverConnectionError(DriverError):
    """Raised when driver fails to connect to gateway."""
    pass


class DeviceNotFound(DriverError):
    """Raised when a device is not found."""
    pass


class DeviceOffline(DriverError):
    """Raised when a device is unreachable."""
    pass


class InvalidStateError(DriverError):
    """Raised when an invalid state is requested."""
    pass
```

---

## How to Add a New Manufacturer

This guide walks through adding support for a new manufacturer (e.g., **Shelly** WiFi devices).

### Step 1: Create the Driver File

```bash
# Create driver directory structure
mkdir -p backend/app/drivers/shelly
touch backend/app/drivers/shelly/__init__.py
touch backend/app/drivers/shelly/driver.py
```

### Step 2: Implement the Driver

```python
# app/drivers/shelly/driver.py
"""
Shelly WiFi Device Driver for MYiot.

Supports: Shelly 1, Shelly 1PM, Shelly 2.5, Shelly Dimmer,
          Shelly RGBW2, Shelly Plug, Shelly H&T

Communication: HTTP REST API + MQTT (optional)
"""

import asyncio
from typing import Any, Optional
import httpx
from app.drivers.base import (
    BaseDriver, DeviceInfo, DeviceState, ProtocolType,
    DeviceCapability, DriverConfigError, DeviceNotFound, DeviceOffline
)
from app.core.events import event_bus
from app.core.logging import logger


class ShellyDriver(BaseDriver):
    """
    Shelly WiFi device driver.
    
    Supports Shelly Gen 1 and Gen 2 devices via HTTP API.
    Auto-discovers devices on the local network using mDNS
    or via user-provided IP addresses.
    """
    
    protocol = ProtocolType.WIFI
    name = "shelly"
    version = "1.0.0"
    capabilities = {
        DeviceCapability.ON_OFF,
        DeviceCapability.DIMMER,
        DeviceCapability.COLOR,
        DeviceCapability.POWER,
        DeviceCapability.ENERGY,
        DeviceCapability.TEMPERATURE,
    }
    
    def __init__(self):
        super().__init__()
        self._devices: dict[str, dict[str, Any]] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._config: dict[str, Any] = {}
    
    async def initialize(self, config: dict[str, Any]) -> None:
        """
        Initialize the Shelly driver.
        
        Config options:
            - discovery_timeout: Seconds to wait for mDNS discovery (default: 30)
            - manual_devices: List of {ip, name} for manual configuration
            - mqtt_topic_prefix: MQTT topic prefix for state updates
            - username: HTTP auth username (optional)
            - password: HTTP auth password (optional)
        """
        self._config = config
        
        # Create HTTP client
        auth = None
        if config.get("username") and config.get("password"):
            auth = httpx.BasicAuth(config["username"], config["password"])
        
        self._http_client = httpx.AsyncClient(
            auth=auth,
            timeout=10.0,
            limits=httpx.Limits(max_connections=50)
        )
        
        logger.info(f"Shelly driver initialized (version {self.version})")
        self._initialized = True
    
    async def discover(self, timeout: int = 30) -> list[DeviceInfo]:
        """
        Discover Shelly devices.
        
        Strategy:
        1. Check manually configured devices
        2. Attempt mDNS discovery on local network
        """
        discovered: list[DeviceInfo] = []
        
        # Check manual devices
        manual = self._config.get("manual_devices", [])
        for device_config in manual:
            try:
                info = await self._probe_device(device_config["ip"])
                if info:
                    discovered.append(info)
            except Exception as e:
                logger.warning(f"Failed to probe {device_config['ip']}: {e}")
        
        # TODO: mDNS discovery using zeroconf
        # This would scan for _http._tcp.local. services
        
        return discovered
    
    async def _probe_device(self, ip: str) -> Optional[DeviceInfo]:
        """Probe a Shelly device at the given IP address."""
        try:
            response = await self._http_client.get(
                f"http://{ip}/shelly",
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Determine device type and capabilities
            device_type = data.get("type", "unknown")
            capabilities = self._map_capabilities(device_type)
            
            return DeviceInfo(
                id=f"shelly_{data.get('mac', ip).replace(':', '')}",
                name=f"Shelly {device_type}",
                manufacturer="Shelly",
                model=device_type,
                protocol=ProtocolType.WIFI,
                type=self._map_device_type(device_type),
                capabilities=[c.value for c in capabilities],
                firmware_version=data.get("fw", "unknown"),
                metadata={"ip_address": ip, "auth": data.get("auth", False)}
            )
            
        except httpx.HTTPError as e:
            logger.debug(f"HTTP error probing {ip}: {e}")
            return None
    
    async def set_state(self, device_id: str, state: dict[str, Any]) -> DeviceState:
        """Send a state update to a Shelly device."""
        device = self._devices.get(device_id)
        if not device:
            raise DeviceNotFound(f"Shelly device {device_id} not found")
        
        ip = device["metadata"]["ip_address"]
        
        try:
            # Build Shelly-specific command
            if "on" in state:
                turn = "on" if state["on"] else "off"
                response = await self._http_client.get(
                    f"http://{ip}/relay/0",
                    params={"turn": turn}
                )
            
            if "brightness" in state:
                brightness = state["brightness"]  # 0-255
                response = await self._http_client.get(
                    f"http://{ip}/light/0",
                    params={"brightness": brightness}
                )
            
            response.raise_for_status()
            
            # Read back the new state
            return await self.get_state(device_id)
            
        except httpx.HTTPError as e:
            raise DeviceOffline(f"Failed to reach {ip}: {e}")
    
    async def get_state(self, device_id: str) -> DeviceState:
        """Read the current state of a Shelly device."""
        device = self._devices.get(device_id)
        if not device:
            raise DeviceNotFound(f"Shelly device {device_id} not found")
        
        ip = device["metadata"]["ip_address"]
        
        try:
            response = await self._http_client.get(
                f"http://{ip}/status",
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Normalize state to MYiot format
            state = self._normalize_state(data)
            
            return DeviceState(
                device_id=device_id,
                state=state,
                available=True
            )
            
        except httpx.HTTPError:
            return DeviceState(
                device_id=device_id,
                state={},
                available=False
            )
    
    async def handle_message(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle MQTT messages from Shelly devices (if MQTT enabled)."""
        # Shelly Gen 2 devices can publish state via MQTT
        # Topic format: shellies/<device-id>/relay/0
        
        if not topic.startswith("shellies/"):
            return
        
        parts = topic.split("/")
        if len(parts) < 3:
            return
        
        device_id = parts[1]
        component = parts[2]
        
        # Emit standardized event
        await event_bus.publish("device_state_changed", {
            "device_id": f"shelly_{device_id}",
            "protocol": self.protocol.value,
            "component": component,
            "payload": payload
        })
    
    async def shutdown(self) -> None:
        """Clean up HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
        self._initialized = False
        logger.info("Shelly driver shut down")
    
    # --- Helper methods ---
    
    def _map_capabilities(self, device_type: str) -> set[DeviceCapability]:
        """Map Shelly device type to capabilities."""
        capability_map = {
            "SHSW-1": {DeviceCapability.ON_OFF},                    # Shelly 1
            "SHSW-PM": {DeviceCapability.ON_OFF, DeviceCapability.POWER},
            "SHSW-25": {DeviceCapability.ON_OFF, DeviceCapability.POWER},
            "SHDM-1": {DeviceCapability.ON_OFF, DeviceCapability.DIMMER},
            "SHRGBW2": {DeviceCapability.ON_OFF, DeviceCapability.DIMMER, DeviceCapability.COLOR},
            "SHPLG-S": {DeviceCapability.ON_OFF, DeviceCapability.POWER, DeviceCapability.ENERGY},
            "SHHT-1": {DeviceCapability.TEMPERATURE, DeviceCapability.HUMIDITY},
        }
        return capability_map.get(device_type, {DeviceCapability.ON_OFF})
    
    def _map_device_type(self, device_type: str) -> str:
        """Map Shelly type to MYiot device type."""
        type_map = {
            "SHSW-1": "switch",
            "SHSW-PM": "switch",
            "SHSW-25": "switch",
            "SHDM-1": "light",
            "SHRGBW2": "light",
            "SHPLG-S": "outlet",
            "SHHT-1": "sensor",
        }
        return type_map.get(device_type, "unknown")
    
    def _normalize_state(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert Shelly state to MYiot standard format."""
        state: dict[str, Any] = {}
        
        if "relays" in data:
            relay = data["relays"][0]
            state["on"] = relay.get("ison", False)
        
        if "meters" in data:
            meter = data["meters"][0]
            state["power"] = meter.get("power", 0)
            state["energy"] = meter.get("total", 0)
        
        if "temperature" in data:
            state["temperature"] = data["temperature"]
        
        if "humidity" in data:
            state["humidity"] = data["humidity"]
        
        return state
```

### Step 3: Register the Driver

```python
# app/drivers/shelly/__init__.py
from app.drivers.shelly.driver import ShellyDriver

__all__ = ["ShellyDriver"]
```

```python
# app/drivers/registry.py
"""Driver registry for MYiot."""

from app.drivers.zigbee.driver import ZigbeeDriver
from app.drivers.zwave.driver import ZWaveDriver
from app.drivers.wifi.driver import WiFiDriver
from app.drivers.ble.driver import BLEDriver
from app.drivers.shelly.driver import ShellyDriver  # <-- Add this

DRIVER_REGISTRY = {
    "zigbee": ZigbeeDriver,
    "zwave": ZWaveDriver,
    "wifi": WiFiDriver,
    "ble": BLEDriver,
    "shelly": ShellyDriver,  # <-- Add this
}

def get_driver(name: str):
    """Get a driver class by name."""
    driver_cls = DRIVER_REGISTRY.get(name)
    if not driver_cls:
        raise ValueError(f"Unknown driver: {name}")
    return driver_cls()
```

### Step 4: Add Configuration

```python
# app/core/config.py — Add to Settings class
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Shelly driver configuration
    SHELLY_ENABLED: bool = False
    SHELLY_DISCOVERY_TIMEOUT: int = 30
    SHELLY_MANUAL_DEVICES: list[dict] = []
    SHELLY_MQTT_TOPIC_PREFIX: str = "shellies"
    SHELLY_USERNAME: Optional[str] = None
    SHELLY_PASSWORD: Optional[str] = None
```

### Step 5: Write Tests

See the [Driver Testing Guide](#driver-testing-guide) section below.

---

## Protocol Implementations

### Zigbee (via Zigbee2MQTT)

```
Protocol:    Zigbee 3.0
Gateway:     Zigbee2MQTT
Hardware:    CC2652P, CC2531, ConBee II, Sonoff ZBDongle
Driver Path: app/drivers/zigbee/
```

**Architecture:**

```
MYiot Backend ◄──► MQTT Broker ◄──► Zigbee2MQTT ◄──► Zigbee Coordinator ◄──► Devices
                      (events)          (control)
```

**Supported Devices:** 3000+ devices via Zigbee2MQTT's device database

**Key Files:**
- `app/drivers/zigbee/driver.py` — Main driver implementation
- `app/drivers/zigbee/converters/` — Message converters per device type
- `app/drivers/zigbee/ota.py` — Over-the-air firmware updates

### Z-Wave (via Z-Wave JS)

```
Protocol:    Z-Wave Plus / Z-Wave 700 / Z-Wave 800 LR
Gateway:     Z-Wave JS
Hardware:    Zooz ZST10-700, Aeotec Z-Stick 7, Silicon Labs UZB7
Driver Path: app/drivers/zwave/
```

**Architecture:**

```
MYiot Backend ◄──► MQTT Broker ◄──► Z-Wave JS UI ◄──► Z-Wave Stick ◄──► Devices
                      (events)         (control)
```

### WiFi (Generic + Vendor-specific)

```
Protocol:    HTTP REST / MQTT / CoAP
Vendors:     Shelly, Tuya, ESPHome, WLED, Wiz
Driver Path: app/drivers/wifi/
```

**Sub-drivers:**

| Vendor | Driver | Communication | Discovery |
|--------|--------|--------------|-----------|
| Shelly | `shelly/driver.py` | HTTP + MQTT | mDNS / Manual |
| Tuya | `tuya/driver.py` | Tuya Cloud API | Cloud pairing |
| ESPHome | `esphome/driver.py` | Native API | mDNS |
| WLED | `wled/driver.py` | HTTP + UDP | mDNS |

### Bluetooth LE

```
Protocol:    Bluetooth Low Energy (BLE)
Gateway:     Built-in (BlueZ on Linux)
Hardware:    Built-in Bluetooth or USB dongle
Driver Path: app/drivers/ble/
```

**Architecture:**

```
MYiot Backend ◄──► Bleak (Python) ◄──► BlueZ / dbus ◄──► Bluetooth Adapter ◄──► Devices
```

**Supported Devices:**

| Device Type | Examples |
|-------------|----------|
| Temperature/Humidity | Xiaomi MiJia, Govee, SwitchBot |
| Presence | Room Assistant, ESPHome BLE beacon |
| Plant Sensors | Xiaomi Flower Care (HHCCJCY01) |

### MQTT (Generic)

```
Protocol:    MQTT 3.1.1 / 5.0
Driver Path: app/drivers/mqtt/
```

The generic MQTT driver allows integration of any MQTT-capable device:

```yaml
# Example: Manual MQTT device configuration
mqtt_devices:
  - name: "Custom Temperature Sensor"
    topic_prefix: "home/sensor/temp1"
    state_topic: "home/sensor/temp1/state"
    command_topic: "home/sensor/temp1/set"
    payload_template:
      temperature: "{{ value_json.temperature }}"
      humidity: "{{ value_json.humidity }}"
    availability_topic: "home/sensor/temp1/availability"
```

---

## Driver Testing Guide

### Unit Tests

Create test files following this pattern:

```python
# tests/drivers/test_shelly.py
"""Tests for the Shelly WiFi driver."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import respx

from app.drivers.shelly.driver import ShellyDriver
from app.drivers.base import DeviceCapability, DeviceNotFound, DeviceOffline


@pytest.fixture
def driver():
    """Create a Shelly driver instance."""
    return ShellyDriver()


@pytest.fixture
def mock_config():
    """Standard test configuration."""
    return {
        "manual_devices": [
            {"ip": "192.168.1.100", "name": "Test Switch"},
            {"ip": "192.168.1.101", "name": "Test Plug"},
        ],
        "discovery_timeout": 5,
    }


class TestShellyDriver:
    """Test suite for ShellyDriver."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, driver, mock_config):
        """Test driver initialization."""
        await driver.initialize(mock_config)
        
        assert driver.is_initialized()
        assert driver._http_client is not None
        assert driver.protocol.value == "wifi"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_discover_manual_devices(self, driver, mock_config):
        """Test discovery of manually configured devices."""
        # Mock Shelly responses
        respx.get("http://192.168.1.100/shelly").mock(return_value=httpx.Response(200, json={
            "type": "SHSW-1",
            "mac": "AABBCCDDEEFF",
            "fw": "20230101"
        }))
        respx.get("http://192.168.1.101/shelly").mock(return_value=httpx.Response(200, json={
            "type": "SHPLG-S",
            "mac": "112233445566",
            "fw": "20230101"
        }))
        
        await driver.initialize(mock_config)
        devices = await driver.discover(timeout=5)
        
        assert len(devices) == 2
        assert devices[0].manufacturer == "Shelly"
        assert devices[0].model == "SHSW-1"
        assert DeviceCapability.ON_OFF.value in devices[0].capabilities
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_discover_offline_device(self, driver, mock_config):
        """Test handling of offline devices during discovery."""
        respx.get("http://192.168.1.100/shelly").mock(
            return_value=httpx.Response(200, json={"type": "SHSW-1", "mac": "AABBCC"})
        )
        respx.get("http://192.168.1.101/shelly").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        
        await driver.initialize(mock_config)
        devices = await driver.discover(timeout=5)
        
        # Should return the one online device
        assert len(devices) == 1
        assert devices[0].model == "SHSW-1"
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_set_state_turn_on(self, driver, mock_config):
        """Test turning a device on."""
        # Setup
        respx.get("http://192.168.1.100/shelly").mock(return_value=httpx.Response(200, json={
            "type": "SHSW-1", "mac": "AABBCCDDEEFF"
        }))
        respx.get("http://192.168.1.100/relay/0").mock(
            return_value=httpx.Response(200, json={"ison": True})
        )
        respx.get("http://192.168.1.100/status").mock(return_value=httpx.Response(200, json={
            "relays": [{"ison": True}],
            "meters": [{"power": 42.5, "total": 1234}]
        }))
        
        await driver.initialize(mock_config)
        devices = await driver.discover()
        driver._devices[devices[0].id] = {
            "metadata": {"ip_address": "192.168.1.100"}
        }
        
        # Execute
        result = await driver.set_state(devices[0].id, {"on": True})
        
        # Verify
        assert result.state["on"] is True
        assert result.available is True
    
    @pytest.mark.asyncio
    async def test_set_state_device_not_found(self, driver, mock_config):
        """Test error when device doesn't exist."""
        await driver.initialize(mock_config)
        
        with pytest.raises(DeviceNotFound):
            await driver.set_state("nonexistent_device", {"on": True})
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_set_state_device_offline(self, driver, mock_config):
        """Test error when device is unreachable."""
        respx.get("http://192.168.1.100/shelly").mock(return_value=httpx.Response(200, json={
            "type": "SHSW-1", "mac": "AABBCCDDEEFF"
        }))
        respx.get("http://192.168.1.100/relay/0").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        
        await driver.initialize(mock_config)
        devices = await driver.discover()
        driver._devices[devices[0].id] = {
            "metadata": {"ip_address": "192.168.1.100"}
        }
        
        with pytest.raises(DeviceOffline):
            await driver.set_state(devices[0].id, {"on": True})
    
    @pytest.mark.asyncio
    async def test_get_state_device_not_found(self, driver, mock_config):
        """Test get_state with unknown device."""
        await driver.initialize(mock_config)
        
        with pytest.raises(DeviceNotFound):
            await driver.get_state("unknown_device")
    
    @pytest.mark.asyncio
    async def test_shutdown(self, driver, mock_config):
        """Test clean shutdown."""
        await driver.initialize(mock_config)
        assert driver.is_initialized()
        
        await driver.shutdown()
        assert not driver.is_initialized()
    
    def test_capability_mapping(self, driver):
        """Test device type to capability mapping."""
        assert DeviceCapability.ON_OFF in driver._map_capabilities("SHSW-1")
        assert DeviceCapability.DIMMER in driver._map_capabilities("SHDM-1")
        assert DeviceCapability.COLOR in driver._map_capabilities("SHRGBW2")
        assert DeviceCapability.POWER in driver._map_capabilities("SHPLG-S")
```

### Integration Tests

For integration tests that communicate with real hardware:

```python
# tests/drivers/integration/test_shelly_live.py
"""
Integration tests for Shelly driver.

These tests require a real Shelly device on the network.
Mark with @pytest.mark.hardware to skip in CI.
"""

import pytest
import os

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hardware,
    pytest.mark.skipif(
        not os.getenv("SHELLY_TEST_IP"),
        reason="Set SHELLY_TEST_IP to run hardware tests"
    ),
]


@pytest.fixture
async def live_driver():
    """Create a driver connected to a real device."""
    from app.drivers.shelly.driver import ShellyDriver
    
    driver = ShellyDriver()
    await driver.initialize({
        "manual_devices": [{"ip": os.getenv("SHELLY_TEST_IP")}]
    })
    
    devices = await driver.discover()
    driver._devices[devices[0].id] = {
        "metadata": {"ip_address": os.getenv("SHELLY_TEST_IP")}
    }
    
    yield driver
    await driver.shutdown()


@pytest.mark.asyncio
async def test_live_device_state(live_driver):
    """Test reading state from a real device."""
    devices = list(live_driver._devices.keys())
    state = await live_driver.get_state(devices[0])
    
    assert state.available is True
    assert "on" in state.state


@pytest.mark.asyncio
async def test_live_toggle_device(live_driver):
    """Test toggling a real device."""
    devices = list(live_driver._devices.keys())
    device_id = devices[0]
    
    # Read current state
    initial = await live_driver.get_state(device_id)
    initial_on = initial.state.get("on", False)
    
    # Toggle
    await live_driver.set_state(device_id, {"on": not initial_on})
    
    # Read new state
    new_state = await live_driver.get_state(device_id)
    assert new_state.state["on"] is not initial_on
    
    # Restore original state
    await live_driver.set_state(device_id, {"on": initial_on})
```

### Running Driver Tests

```bash
# Run all driver tests
cd backend
pytest tests/drivers/ -v

# Run unit tests only
pytest tests/drivers/ -m "not integration" -v

# Run with hardware tests
SHELLY_TEST_IP=192.168.1.100 pytest tests/drivers/ -m "hardware" -v

# Run with coverage
pytest tests/drivers/ --cov=app.drivers --cov-report=term-missing
```

---

## Driver Registration

Drivers are auto-discovered at startup:

```python
# app/drivers/registry.py
"""Driver registry with auto-discovery."""

from typing import Type
from app.drivers.base import BaseDriver
from app.core.logging import logger

# Import all available drivers
from app.drivers.zigbee.driver import ZigbeeDriver
from app.drivers.zwave.driver import ZWaveDriver
from app.drivers.wifi.driver import WiFiDriver
from app.drivers.ble.driver import BLEDriver
from app.drivers.mqtt.driver import MQTTDriver
from app.drivers.shelly.driver import ShellyDriver
from app.drivers.tuya.driver import TuyaDriver
from app.drivers.esphome.driver import ESPHomeDriver

DRIVER_REGISTRY: dict[str, Type[BaseDriver]] = {
    ZigbeeDriver.protocol.value: ZigbeeDriver,
    ZWaveDriver.protocol.value: ZWaveDriver,
    WiFiDriver.protocol.value: WiFiDriver,
    BLEDriver.protocol.value: BLEDriver,
    MQTTDriver.protocol.value: MQTTDriver,
    ShellyDriver.name: ShellyDriver,
    TuyaDriver.name: TuyaDriver,
    ESPHomeDriver.name: ESPHomeDriver,
}


def get_available_drivers() -> list[str]:
    """List all registered driver names."""
    return list(DRIVER_REGISTRY.keys())


def get_driver(name: str) -> BaseDriver:
    """
    Instantiate a driver by name.
    
    Args:
        name: Driver name (matches protocol value or driver name)
        
    Returns:
        Instantiated driver
        
    Raises:
        ValueError: If driver is not found
    """
    driver_cls = DRIVER_REGISTRY.get(name.lower())
    if not driver_cls:
        available = ", ".join(get_available_drivers())
        raise ValueError(f"Unknown driver '{name}'. Available: {available}")
    
    return driver_cls()


async def initialize_all(config: dict) -> dict[str, BaseDriver]:
    """
    Initialize all enabled drivers.
    
    Returns:
        Dictionary of initialized driver instances
    """
    drivers: dict[str, BaseDriver] = {}
    
    for name, driver_cls in DRIVER_REGISTRY.items():
        driver_config = config.get(name, {})
        
        # Check if driver is enabled
        if not driver_config.get("enabled", True):
            logger.info(f"Driver '{name}' is disabled, skipping")
            continue
        
        try:
            logger.info(f"Initializing driver: {name}")
            driver = driver_cls()
            await driver.initialize(driver_config)
            drivers[name] = driver
            logger.info(f"Driver '{name}' initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize driver '{name}': {e}")
            # Continue with other drivers — don't fail the entire system
    
    return drivers
```

---

## Reference: Existing Drivers

### Zigbee Driver

```
File:        app/drivers/zigbee/driver.py
Protocol:    Zigbee 3.0
Gateway:     Zigbee2MQTT
MQTT Topics: zigbee2mqtt/#
Features:    Discovery, OTA updates, Group control, Bindings
```

### Z-Wave Driver

```
File:        app/drivers/zwave/driver.py
Protocol:    Z-Wave / Z-Wave Plus / Z-Wave 700
Gateway:     Z-Wave JS
API:         zwave-js-server (WebSocket)
Features:    Inclusion, Exclusion, Association, Configuration
```

### WiFi Driver

```
File:        app/drivers/wifi/driver.py
Protocol:    HTTP REST / MQTT
Sub-drivers: Shelly, Tuya, ESPHome, WLED
Discovery:   mDNS, Manual IP, Cloud API
```

### BLE Driver

```
File:        app/drivers/ble/driver.py
Protocol:    Bluetooth LE
Library:     Bleak (async Bluetooth)
Discovery:   Passive scanning, Active scanning
```

---

*For questions about driver development, join us on [Discord](https://discord.gg/myiot) or open a [Discussion](https://github.com/myiot/myiot/discussions).*
