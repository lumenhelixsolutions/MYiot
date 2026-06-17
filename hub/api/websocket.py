"""
WebSocket handler for Smart Home Universal Hub.

Provides real-time bidirectional communication for state updates and
command execution. Clients subscribe to state changes via the registry
and can send commands back through the WebSocket connection.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.base_driver import DeviceState

logger = logging.getLogger(__name__)

router = APIRouter()


class WebSocketClient:
    """
    Represents a connected WebSocket client session.

    Manages subscription to state registry changes and handles cleanup
    on disconnect.
    """

    def __init__(self, websocket: WebSocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self._listener_callback: Optional[Any] = None
        self._connected = False

    async def on_state_change(self, device_id: str, state: DeviceState) -> None:
        """
        Callback invoked when any device state changes in the registry.

        Sends a JSON message to the client with the updated state.

        Args:
            device_id: Unique identifier of the device that changed.
            state: The new DeviceState.
        """
        if not self._connected:
            return
        try:
            await self.websocket.send_json({
                "type": "state_change",
                "device_id": device_id,
                "state": state.model_dump(),
            })
        except Exception as exc:
            logger.debug(
                "Failed to send state change to client %s: %s",
                self.client_id,
                exc,
            )

    async def send(self, message: Dict[str, Any]) -> None:
        """Send a JSON message to the client."""
        if self._connected:
            await self.websocket.send_json(message)

    def set_connected(self, connected: bool) -> None:
        """Update the connection status."""
        self._connected = connected


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time device state updates.

    On connection, subscribes to all state registry changes and pushes
    updates to the client. Accepts incoming command messages from the
    client and dispatches them to the appropriate device.

    Message protocol:
        Client -> Server:
            {"action": "command", "device_id": "...", "payload": {...}}
            {"action": "subscribe", "device_type": "plug|light|thermostat|camera"}
            {"action": "ping"}

        Server -> Client:
            {"type": "state_change", "device_id": "...", "state": {...}}
            {"type": "command_result", "device_id": "...", "result": {...}}
            {"type": "pong"}
            {"type": "error", "message": "..."}
    """
    client_id = (
        f"{websocket.client.host}:{websocket.client.port}"
        if websocket.client
        else "unknown"
    )
    await websocket.accept()

    client = WebSocketClient(websocket, client_id)
    client.set_connected(True)

    registry = websocket.app.state.registry
    device_manager = websocket.app.state.device_manager

    # Subscribe to state changes
    listener = client.on_state_change
    registry.subscribe(listener)

    logger.info("WebSocket client %s connected", client_id)

    try:
        while True:
            message = await websocket.receive_json()
            await _handle_client_message(message, client, registry, device_manager)
    except WebSocketDisconnect:
        logger.info("WebSocket client %s disconnected", client_id)
    except asyncio.CancelledError:
        logger.debug("WebSocket client %s cancelled", client_id)
    except Exception as exc:
        logger.warning("WebSocket error for client %s: %s", client_id, exc)
    finally:
        # Cleanup: unsubscribe from registry
        client.set_connected(False)
        registry.unsubscribe(listener)
        logger.debug("WebSocket client %s cleaned up", client_id)


async def _handle_client_message(
    message: Dict[str, Any],
    client: WebSocketClient,
    registry: Any,
    device_manager: Any,
) -> None:
    """
    Handle an incoming message from a WebSocket client.

    Args:
        message: Parsed JSON message from the client.
        client: The WebSocket client wrapper.
        registry: The state registry instance.
        device_manager: The device manager instance.
    """
    action = message.get("action")

    if action == "command":
        await _handle_command_message(message, client, registry, device_manager)
    elif action == "subscribe":
        await _handle_subscribe_message(message, client, registry)
    elif action == "ping":
        await client.send({"type": "pong", "timestamp": asyncio.get_event_loop().time()})
    else:
        await client.send({"type": "error", "message": f"Unknown action: {action}"})


async def _handle_command_message(
    message: Dict[str, Any],
    client: WebSocketClient,
    registry: Any,
    device_manager: Any,
) -> None:
    """Handle a command message from the client via the DeviceManager."""
    device_id = message.get("device_id")
    payload = message.get("payload", {})

    if not device_id:
        await client.send({"type": "error", "message": "Missing device_id in command"})
        return

    device = await registry.get(device_id)
    if not device:
        await client.send({
            "type": "error",
            "message": f"Device not found: {device_id}",
        })
        return

    try:
        success = await device_manager.set_state(device_id, payload)
        await client.send({
            "type": "command_result",
            "device_id": device_id,
            "success": success,
        })
    except Exception as exc:
        logger.warning("WebSocket command failed for %s: %s", device_id, exc)
        await client.send({
            "type": "command_result",
            "device_id": device_id,
            "success": False,
            "error": str(exc),
        })


async def _handle_subscribe_message(
    message: Dict[str, Any],
    client: WebSocketClient,
    registry: Any,
) -> None:
    """
    Handle a subscribe message from the client.

    Sends the current state of all devices matching the subscription
    criteria to the client as initial data.
    """
    device_type = message.get("device_type")

    # Send current state of matching devices as initial snapshot
    states = await registry.get_all(device_type)
    for state in states:
        await client.on_state_change(state.device_id, state)

    await client.send({
        "type": "subscribed",
        "device_type": device_type,
        "count": len(states),
    })
