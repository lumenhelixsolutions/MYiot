"""Simulator plugin with mock devices for demo and testing."""

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional

from core.base_driver import BaseDriver, DeviceState
from core.payloads import (
    SmartPlugPayload,
    SmartLightPayload,
    ThermostatPayload,
    CameraPayload,
)

logger = logging.getLogger(__name__)


class SimulatorDevice:
    """Helper class representing a single simulated device."""

    def __init__(
        self,
        device_id: str,
        name: str,
        manufacturer: str,
        model: str,
        device_type: str,
        initial_state: Dict[str, Any],
    ):
        self.device_id = device_id
        self.name = name
        self.manufacturer = manufacturer
        self.model = model
        self.device_type = device_type
        self._state = initial_state
        self.online = True
        self.last_updated = time.time()

    @property
    def state(self) -> Dict[str, Any]:
        """Return current device state with minor randomized variations."""
        now = time.time()
        # Simulate minor fluctuations based on device type
        if self.device_type == "thermostat":
            current = self._state.get("current_temp", 72.0)
            drift = random.uniform(-0.2, 0.2)
            self._state["current_temp"] = round(current + drift, 1)
        elif self.device_type == "light" and self._state.get("power", False):
            # Randomly flicker brightness by +/- 1%
            bri = self._state.get("brightness", 50)
            self._state["brightness"] = max(0, min(100, bri + random.randint(-1, 1)))
        self.last_updated = now
        return dict(self._state)

    def update_state(self, payload: Dict[str, Any]) -> None:
        """Update internal state from a standardized payload."""
        for key, value in payload.items():
            if value is not None:
                self._state[key] = value
        self.last_updated = time.time()

    def to_device_state(self) -> DeviceState:
        """Convert to standardized DeviceState."""
        return DeviceState(
            device_id=self.device_id,
            manufacturer=self.manufacturer,
            model=self.model,
            device_type=self.device_type,
            online=self.online,
            state=self.state,
            last_updated=self.last_updated,
        )


def create_simulated_devices() -> List[SimulatorDevice]:
    """Factory function that creates a suite of simulated devices."""
    devices = [
        # -- Smart Plugs (2) --
        SimulatorDevice(
            device_id="sim-plug-01",
            name="Living Room Plug",
            manufacturer="simulator",
            model="SimPlug-v1",
            device_type="plug",
            initial_state={"power": True, "energy_w": 42.5},
        ),
        SimulatorDevice(
            device_id="sim-plug-02",
            name="Office Plug",
            manufacturer="simulator",
            model="SimPlug-v2",
            device_type="plug",
            initial_state={"power": False, "energy_w": 0.0},
        ),
        # -- Smart Lights (3) --
        SimulatorDevice(
            device_id="sim-light-01",
            name="Bedroom Lamp",
            manufacturer="simulator",
            model="SimBulb-RGB",
            device_type="light",
            initial_state={"power": True, "brightness": 75, "color": "#ffaa00"},
        ),
        SimulatorDevice(
            device_id="sim-light-02",
            name="Kitchen Strip",
            manufacturer="simulator",
            model="SimStrip-LED",
            device_type="light",
            initial_state={"power": True, "brightness": 100, "color": (255, 255, 255)},
        ),
        SimulatorDevice(
            device_id="sim-light-03",
            name="Porch Light",
            manufacturer="simulator",
            model="SimBulb-Dimmable",
            device_type="light",
            initial_state={"power": False, "brightness": 0, "color": "#ffffff"},
        ),
        # -- Thermostats (2) --
        SimulatorDevice(
            device_id="sim-tstat-01",
            name="Main Floor Thermostat",
            manufacturer="simulator",
            model="SimStat-Pro",
            device_type="thermostat",
            initial_state={
                "mode": "auto",
                "target_temp": 72.0,
                "current_temp": 71.4,
                "humidity": 45,
            },
        ),
        SimulatorDevice(
            device_id="sim-tstat-02",
            name="Upstairs Thermostat",
            manufacturer="simulator",
            model="SimStat-Lite",
            device_type="thermostat",
            initial_state={
                "mode": "heat",
                "target_temp": 68.0,
                "current_temp": 67.8,
                "humidity": 38,
            },
        ),
        # -- Camera (1) --
        SimulatorDevice(
            device_id="sim-cam-01",
            name="Front Door Camera",
            manufacturer="simulator",
            model="SimCam-HD",
            device_type="camera",
            initial_state={"power": True, "recording": True, "motion_detected": False},
        ),
    ]
    logger.info("Created %d simulated devices", len(devices))
    return devices


class SimulatorPlugin(BaseDriver):
    """Simulator plugin driver for demo and testing purposes.

    Simulates 8+ devices across all 4 types:
      - 2 smart plugs
      - 3 smart lights
      - 2 thermostats
      - 1 camera
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._devices: List[SimulatorDevice] = []
        self._device_map: Dict[str, SimulatorDevice] = {}
        self._authenticated = False

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Simulator authentication always succeeds."""
        logger.info("SimulatorPlugin: authenticate() called — always True")
        self._devices = create_simulated_devices()
        self._device_map = {d.device_id: d for d in self._devices}
        self._authenticated = True
        self._connected = True
        return True

    async def get_state(self) -> DeviceState:
        """Return current state of the primary device or first simulated device."""
        if not self._authenticated:
            await self.authenticate({})
        device = self._device_map.get(self.device_id)
        if device is None:
            # Fallback: create a single generic simulated device
            device = SimulatorDevice(
                device_id=self.device_id,
                name=f"Sim {self.device_type}",
                manufacturer="simulator",
                model="SimGeneric",
                device_type=self.device_type,
                initial_state={"power": True},
            )
            self._device_map[self.device_id] = device
        return device.to_device_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Update internal state from a standardized payload."""
        if not self._authenticated:
            await self.authenticate({})
        device = self._device_map.get(self.device_id)
        if device is None:
            logger.warning("Device %s not found in simulator", self.device_id)
            return False
        try:
            device.update_state(payload)
            logger.info("SimulatorPlugin: set_state(%s) -> %s", self.device_id, payload)
            return True
        except Exception as exc:
            logger.error("SimulatorPlugin: set_state failed: %s", exc)
            return False

    async def disconnect(self) -> None:
        """No-op disconnect for simulator."""
        self._connected = False
        self._authenticated = False
        logger.info("SimulatorPlugin: disconnect() called")

    async def capture_snapshot(self) -> Optional[bytes]:
        """Return None — placeholder for camera snapshot."""
        return None

    async def get_stream_url(self) -> Optional[str]:
        """Return a mock RTSP URL for cameras."""
        if self.device_type == "camera":
            return f"rtsp://simulator.local/{self.device_id}/live"
        return None
