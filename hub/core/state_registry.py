"""
In-memory state registry for Smart Home Universal Hub.

Provides a lightweight, centralized, thread-safe state dictionary that holds
the current status of all discovered devices. Uses a pub/sub pattern to
notify listeners of state changes in real-time.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Union

from core.base_driver import DeviceState

logger = logging.getLogger(__name__)

# Type alias for event listener callbacks
StateListener = Callable[[str, DeviceState], Union[None, Any]]


class StateRegistry:
    """
    Lightweight, centralized in-memory state dictionary.

    Holds current status of all discovered devices. Updated from incoming
    broadcast data (event-driven) and via explicit API calls. Thread-safe
    via asyncio.Lock. Supports pub/sub pattern for real-time state change
    notifications.
    """

    def __init__(self) -> None:
        """Initialize the state registry with empty state and no listeners."""
        self._state: Dict[str, DeviceState] = {}
        self._listeners: List[StateListener] = []
        self._lock = asyncio.Lock()

    async def update(self, device_id: str, state: DeviceState) -> None:
        """
        Update device state and notify all registered listeners.

        Args:
            device_id: Unique identifier of the device.
            state: The new DeviceState to store.
        """
        async with self._lock:
            self._state[device_id] = state
        await self._notify(device_id, state)

    async def get(self, device_id: str) -> Optional[DeviceState]:
        """
        Get current state for a specific device.

        Args:
            device_id: Unique identifier of the device.

        Returns:
            The DeviceState for the device, or None if not found.
        """
        return self._state.get(device_id)

    async def get_all(self, device_type: Optional[str] = None) -> List[DeviceState]:
        """
        Get all registered devices, optionally filtered by device type.

        Args:
            device_type: Optional filter for device type
                ("plug", "light", "thermostat", "camera").

        Returns:
            List of DeviceState objects matching the filter criteria.
        """
        states = list(self._state.values())
        if device_type:
            states = [s for s in states if s.device_type == device_type]
        return states

    async def remove(self, device_id: str) -> bool:
        """
        Remove a device from the registry.

        Args:
            device_id: Unique identifier of the device to remove.

        Returns:
            True if the device was found and removed, False otherwise.
        """
        async with self._lock:
            if device_id in self._state:
                del self._state[device_id]
                return True
            return False

    def subscribe(self, callback: StateListener) -> None:
        """
        Subscribe to state change events.

        The callback will be invoked whenever any device's state is updated.
        Both synchronous and asynchronous callbacks are supported.

        Args:
            callback: Function or coroutine to call with (device_id, state)
                on each state change.
        """
        self._listeners.append(callback)

    def unsubscribe(self, callback: StateListener) -> bool:
        """
        Unsubscribe a previously registered listener.

        Args:
            callback: The callback function to remove.

        Returns:
            True if the callback was found and removed, False otherwise.
        """
        if callback in self._listeners:
            self._listeners.remove(callback)
            return True
        return False

    async def _notify(self, device_id: str, state: DeviceState) -> None:
        """
        Notify all registered listeners of a state change.

        Handles both synchronous and asynchronous callbacks safely,
        catching and logging any exceptions to prevent listener errors
        from crashing the registry.

        Args:
            device_id: Unique identifier of the device that changed.
            state: The new DeviceState.
        """
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(device_id, state)
                else:
                    listener(device_id, state)
            except Exception as exc:
                logger.warning(
                    "State listener '%s' raised an exception: %s",
                    getattr(listener, "__name__", repr(listener)),
                    exc,
                    exc_info=True,
                )

    def __len__(self) -> int:
        """Return the number of devices currently in the registry."""
        return len(self._state)

    def __contains__(self, device_id: str) -> bool:
        """Check if a device is registered."""
        return device_id in self._state
