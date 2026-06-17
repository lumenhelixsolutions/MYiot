"""
Abstract base driver interface for Smart Home Universal Hub.

Every manufacturer plugin must inherit from BaseDriver and implement
all abstract methods for authentication, state retrieval, state setting,
and disconnection.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class DeviceState(BaseModel):
    """Standardized device state model representing the current status of a device."""

    device_id: str
    manufacturer: str
    model: str
    device_type: str  # "plug" | "light" | "thermostat" | "camera"
    online: bool
    state: Dict[str, Any]
    last_updated: float  # Unix timestamp


class BaseDriver(ABC):
    """
    Abstract base class for all manufacturer-specific device drivers.

    Provides a unified interface for device authentication, state polling,
    state modification, and disconnection. Optional methods for camera
    devices (snapshot capture and stream URL retrieval) are provided with
    default no-op implementations.
    """

    def __init__(self, device_config: Dict[str, Any]):
        """
        Initialize the driver with device configuration.

        Args:
            device_config: Dictionary containing device configuration including
                device_id, manufacturer, model, device_type, and other
                manufacturer-specific settings.
        """
        self.config = device_config
        self.device_id = device_config["device_id"]
        self.manufacturer = device_config["manufacturer"]
        self.model = device_config.get("model", "unknown")
        self.device_type = device_config["device_type"]
        self._session: Any = None
        self._connected = False

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with the device or cloud API.

        Handles authentication using local network tokens, bridge tokens,
        OAuth2 tokens, API keys, or username/password pairs depending on
        the manufacturer's authentication type.

        Args:
            credentials: Dictionary containing authentication credentials
                specific to the manufacturer (e.g., bridge token, API key,
                username/password, OAuth token).

        Returns:
            True if authentication was successful, False otherwise.
        """
        ...

    @abstractmethod
    async def get_state(self) -> DeviceState:
        """
        Poll the device and return its current state.

        Retrieves the current state from the device, translates it to the
        standardized DeviceState format, and returns it.

        Returns:
            DeviceState representing the current device status.

        Raises:
            ConnectionError: If the device cannot be reached.
            RuntimeError: If authentication has failed or expired.
        """
        ...

    @abstractmethod
    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """
        Send a command to the device to change its state.

        Receives a standardized payload dictionary, translates it to the
        manufacturer-specific command format, and sends it to the device.

        Args:
            payload: Dictionary containing the desired state changes
                (e.g., {"power": True}, {"brightness": 50, "color": "#ff0000"}).

        Returns:
            True if the command was executed successfully, False otherwise.

        Raises:
            ConnectionError: If the device cannot be reached.
            ValueError: If the payload contains invalid values.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Safely close any active sessions, sockets, or connections.

        Should be called during shutdown or when the device is being removed.
        All network resources should be released after this call.
        """
        ...

    # --- Optional methods (override for camera devices) ---

    async def capture_snapshot(self) -> Optional[bytes]:
        """
        Request a single static image frame from a camera device.

        Returns:
            JPEG/PNG image data as bytes, or None if not supported.
        """
        return None

    async def get_stream_url(self) -> Optional[str]:
        """
        Get the RTSP or WebRTC stream URI for a camera device.

        Returns:
            Stream URL string (e.g., "rtsp://192.168.1.100/stream"),
            or None if not supported.
        """
        return None
