"""
FastAPI REST API routes for Smart Home Universal Hub.

Provides all HTTP endpoints for device management, manufacturer listing,
credential storage, camera stream access, and event log retrieval.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from auth.session import (
    AuthenticatedUser,
    clear_auth_cookie,
    create_access_token,
    hash_password,
    require_auth,
    set_auth_cookie,
    verify_password,
)
from core.base_driver import DeviceState
from core.manufacturer_maps import MANUFACTURER_MAPS
from models.database import (
    DeviceConfig,
    EventLog,
    get_db_session,
    log_event,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Request/Response Models ──────────────────────────────────────────────


class DeviceCommandRequest(BaseModel):
    """Request body for sending a command to a device."""
    payload: Dict[str, Any]


class ManualDeviceRequest(BaseModel):
    """Request body for manually adding a device."""
    device_id: str
    manufacturer: str
    model: Optional[str] = "unknown"
    device_type: str
    ip_address: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = "rest"
    auth_type: Optional[str] = None
    credentials_key: Optional[str] = None
    custom_map: Optional[Dict[str, Any]] = None
    room: Optional[str] = None
    name: Optional[str] = None


class CredentialsRequest(BaseModel):
    """Request body for storing manufacturer credentials."""
    credentials: Dict[str, Any]


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class StreamResponse(BaseModel):
    """Response model for camera stream URI."""
    stream_url: Optional[str] = None


# ─── Device Management Routes ─────────────────────────────────────────────


@router.get("/api/devices")
async def list_devices(
    request: Request,
    device_type: Optional[str] = Query(None, description="Filter by device type"),
) -> List[DeviceState]:
    """
    List all discovered devices with optional type filter.

    Returns:
        List of DeviceState objects from the in-memory registry.
    """
    registry = request.app.state.registry
    states = await registry.get_all(device_type)
    return states


@router.get("/api/devices/{device_id}")
async def get_device(
    request: Request,
    device_id: str,
) -> DeviceState:
    """
    Get the current state for a specific device.

    Args:
        device_id: Unique identifier of the device.

    Returns:
        DeviceState for the requested device.

    Raises:
        HTTPException(404): If the device is not found.
    """
    registry = request.app.state.registry
    state = await registry.get(device_id)
    if not state:
        raise HTTPException(status_code=404, detail="Device not found")
    return state


@router.post("/api/devices/{device_id}/command")
async def send_command(
    request: Request,
    device_id: str,
    command: DeviceCommandRequest,
) -> Dict[str, Any]:
    """
    Send a command to a device.

    Args:
        device_id: Unique identifier of the device.
        command: Command request containing the payload to send.

    Returns:
        Dispatcher result with success status and response/error.

    Raises:
        HTTPException(404): If the device is not found.
        HTTPException(502): If command dispatch fails or raises an exception.
    """
    registry = request.app.state.registry

    device = await registry.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    manager = request.app.state.device_manager
    try:
        success = await manager.set_state(device_id, command.payload)
    except Exception as exc:
        logger.warning("set_state raised an exception for %s: %s", device_id, exc)
        # Log the failure
        try:
            async for session in get_db_session():
                await log_event(
                    session,
                    event_type="command",
                    device_id=device_id,
                    manufacturer=device.manufacturer,
                    details={"command": command.payload, "success": False, "error": str(exc)},
                )
                break
        except Exception as log_exc:
            logger.warning("Failed to log command event: %s", log_exc)
        raise HTTPException(status_code=502, detail=str(exc))

    # Log the command
    try:
        async for session in get_db_session():
            await log_event(
                session,
                event_type="command",
                device_id=device_id,
                manufacturer=device.manufacturer,
                details={"command": command.payload, "success": success},
            )
            break
    except Exception as exc:
        logger.warning("Failed to log command event: %s", exc)

    if not success:
        raise HTTPException(status_code=502, detail="Command failed")

    return {"success": True, "device_id": device_id}


@router.post("/api/devices/manual")
async def add_manual_device(
    request: Request,
    config: ManualDeviceRequest,
) -> Dict[str, Any]:
    """
    Manually add a device by configuration.

    Creates a DeviceState entry in the registry and persists the
    configuration to the database.

    Args:
        config: Device configuration including device_id, manufacturer,
            device_type, and optional network/auth details.

    Returns:
        Success response with the added device_id.
    """
    registry = request.app.state.registry

    # Create device state in registry
    device_state = DeviceState(
        device_id=config.device_id,
        manufacturer=config.manufacturer,
        model=config.model or "unknown",
        device_type=config.device_type,
        online=True,
        state={
            "ip_address": config.ip_address,
            "port": config.port,
            "protocol": config.protocol,
        },
        last_updated=time.time(),
    )
    await registry.update(config.device_id, device_state)

    # Persist to database
    device_config = None
    try:
        async for session in get_db_session():
            device_config = DeviceConfig(
                device_id=config.device_id,
                manufacturer=config.manufacturer,
                model=config.model,
                device_type=config.device_type,
                ip_address=config.ip_address,
                port=config.port,
                protocol=config.protocol,
                auth_type=config.auth_type,
                credentials_key=config.credentials_key,
                custom_map=config.custom_map,
                room=config.room,
                name=config.name or config.device_id,
                enabled=True,
            )
            session.add(device_config)
            await session.commit()

            # Log the discovery event
            await log_event(
                session,
                event_type="manual_add",
                device_id=config.device_id,
                manufacturer=config.manufacturer,
                details={"ip": config.ip_address, "model": config.model},
            )
            break
    except Exception as exc:
        logger.warning("Failed to persist manual device to DB: %s", exc)
        return {"success": True, "device_id": config.device_id}

    # Register the driver so commands can be dispatched immediately
    if device_config is not None:
        try:
            manager = request.app.state.device_manager
            await manager.add_device(device_config)
        except Exception as exc:
            logger.warning(
                "Failed to register driver for manual device %s: %s",
                config.device_id,
                exc,
            )

    return {"success": True, "device_id": config.device_id}


@router.delete("/api/devices/{device_id}")
async def remove_device(
    request: Request,
    device_id: str,
) -> Dict[str, Any]:
    """
    Remove a device from the hub.

    Removes the device from the in-memory registry and the database.

    Args:
        device_id: Unique identifier of the device to remove.

    Returns:
        Success response confirming deletion.

    Raises:
        HTTPException(404): If the device is not found.
    """
    registry = request.app.state.registry

    state = await registry.get(device_id)
    if not state:
        raise HTTPException(status_code=404, detail="Device not found")

    await registry.remove(device_id)

    # Remove from database
    try:
        async for session in get_db_session():
            result = await session.execute(
                select(DeviceConfig).where(DeviceConfig.device_id == device_id)
            )
            db_device = result.scalar_one_or_none()
            if db_device:
                await session.delete(db_device)
                await session.commit()

            await log_event(
                session,
                event_type="device_removed",
                device_id=device_id,
                manufacturer=state.manufacturer,
            )
            break
    except Exception as exc:
        logger.warning("Failed to remove device from DB: %s", exc)

    # Disconnect the driver so it stops accepting commands
    try:
        manager = request.app.state.device_manager
        await manager.remove_device(device_id)
    except Exception as exc:
        logger.warning("Failed to disconnect driver for %s: %s", device_id, exc)

    return {"success": True, "device_id": device_id}


# ─── Manufacturer Routes ──────────────────────────────────────────────────


@router.get("/api/manufacturers")
async def list_manufacturers() -> Dict[str, Dict[str, Any]]:
    """
    List all supported manufacturers with their configurations.

    Returns:
        Dictionary mapping manufacturer key to configuration details.
    """
    return MANUFACTURER_MAPS


# ─── Authentication Routes ────────────────────────────────────────────────


@router.post("/api/auth/{manufacturer}")
async def store_credentials(
    request: Request,
    manufacturer: str,
    creds: CredentialsRequest,
) -> Dict[str, Any]:
    """
    Store authentication credentials for a manufacturer.

    Args:
        manufacturer: Manufacturer key (e.g., "philips_hue", "nest").
        creds: Credentials dictionary containing auth tokens/keys.

    Returns:
        Success response confirming storage.

    Raises:
        HTTPException(400): If manufacturer is not supported.
    """
    if manufacturer not in MANUFACTURER_MAPS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported manufacturer: {manufacturer}",
        )

    auth = request.app.state.auth_manager
    auth.store(manufacturer, creds.credentials)

    return {"success": True, "manufacturer": manufacturer}


# ─── Camera Stream Routes ─────────────────────────────────────────────────


@router.get("/api/streams/{device_id}")
async def get_stream_uri(
    request: Request,
    device_id: str,
) -> StreamResponse:
    """
    Get the RTSP/WebRTC stream URI for a camera device.

    Args:
        device_id: Unique identifier of the camera device.

    Returns:
        StreamResponse containing the stream URL if available.

    Raises:
        HTTPException(404): If the device is not found or not a camera.
    """
    registry = request.app.state.registry
    device = await registry.get(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.device_type != "camera":
        raise HTTPException(
            status_code=400,
            detail=f"Device is not a camera (type: {device.device_type})",
        )

    # Try to get stream URL from device state
    stream_url = device.state.get("stream_url")

    # If not in state, try manufacturer map defaults
    if not stream_url:
        mfr_config = MANUFACTURER_MAPS.get(device.manufacturer, {})
        base_template = mfr_config.get("base_url_template", "")
        endpoints = mfr_config.get("endpoints", {})
        ip = device.state.get("ip")
        if base_template and ip and "stream" in endpoints:
            stream_url = base_template.format(ip=ip) + endpoints["stream"]

    return StreamResponse(stream_url=stream_url)


@router.post("/api/streams/{device_id}/refresh")
async def refresh_stream_uri(request: Request, device_id: str) -> StreamResponse:
    """Re-resolve the stream URL from the driver and update the registry."""
    registry = request.app.state.registry
    device = await registry.get(device_id)
    if not device or device.device_type != "camera":
        raise HTTPException(status_code=404, detail="Camera not found")

    manager = request.app.state.device_manager
    driver = None
    async with manager._lock:
        driver = manager._drivers.get(device_id)

    stream_url = None
    if driver is not None:
        try:
            stream_url = await driver.get_stream_url()
            new_state = await driver.get_state()
            if new_state:
                await registry.update(device_id, new_state)
        except Exception as exc:
            logger.warning("Failed to refresh stream for %s: %s", device_id, exc)
            raise HTTPException(status_code=502, detail=str(exc))

    return StreamResponse(stream_url=stream_url)


# ─── Event Log Routes ─────────────────────────────────────────────────────


@router.get("/api/logs")
async def get_logs(
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Number of entries to return"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
) -> Dict[str, Any]:
    """
    Get the event log with pagination and optional filtering.

    Args:
        limit: Maximum number of log entries to return (1-1000).
        offset: Number of entries to skip for pagination.
        event_type: Optional filter by event type.
        device_id: Optional filter by device ID.

    Returns:
        Paginated response with log entries and total count.
    """
    try:
        async for session in get_db_session():
            # Build query
            query = select(EventLog).order_by(desc(EventLog.timestamp))

            if event_type:
                query = query.where(EventLog.event_type == event_type)
            if device_id:
                query = query.where(EventLog.device_id == device_id)

            # Get total count
            count_query = select(func.count(EventLog.id))
            if event_type:
                count_query = count_query.where(EventLog.event_type == event_type)
            if device_id:
                count_query = count_query.where(EventLog.device_id == device_id)

            count_result = await session.execute(count_query)
            total = count_result.scalar() or 0

            # Get paginated results
            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            logs = [row.to_dict() for row in result.scalars().all()]

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "logs": logs,
            }
    except Exception as exc:
        logger.error("Failed to retrieve event logs: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve logs: {exc}",
        )
