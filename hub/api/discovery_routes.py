"""REST API routes for global IoT device discovery."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.base_driver import DeviceState
from core.manufacturer_maps import MANUFACTURER_MAPS
from models.database import DeviceConfig, get_db_session, log_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


class RegisterDiscoveryRequest(BaseModel):
    """Register a discovered device onto the hub."""

    name: Optional[str] = None
    room: Optional[str] = "Unassigned"


def _display_manufacturer(key: str) -> str:
    config = MANUFACTURER_MAPS.get(key, {})
    return config.get("display_name", key.replace("_", " ").title())


def _serialize_pending(raw: Dict[str, Any]) -> Dict[str, Any]:
    manufacturer = raw.get("manufacturer", "unknown")
    device_type = raw.get("device_type", "unknown")
    ip = raw.get("ip_address", "")
    stream_url = None
    if device_type == "camera" and ip:
        stream_url = f"rtsp://{ip}:554/live"

    return {
        "id": raw.get("id") or raw.get("device_id"),
        "device_id": raw.get("device_id") or raw.get("id"),
        "name": raw.get("name") or raw.get("device_id"),
        "manufacturer": _display_manufacturer(manufacturer),
        "manufacturer_key": manufacturer,
        "model": raw.get("model", "unknown"),
        "type": device_type,
        "device_type": device_type,
        "ip_address": ip,
        "protocol": raw.get("protocol", "SSDP"),
        "mac_address": raw.get("mac_address", ""),
        "firmware": raw.get("firmware", "unknown"),
        "signal_strength": raw.get("signal_strength", 0),
        "scan_phase": raw.get("scan_phase", "probing"),
        "stream_url": stream_url,
        "discovered_at": raw.get("discovered_at"),
        "last_seen": raw.get("last_seen"),
    }


@router.get("/status")
async def discovery_status(request: Request) -> Dict[str, Any]:
    """Return active scan progress and pending device count."""
    discovery = request.app.state.discovery
    return discovery.get_scan_status()


@router.get("/devices")
async def list_discovered_devices(request: Request) -> List[Dict[str, Any]]:
    """List devices found by the scanner that are not yet registered."""
    discovery = request.app.state.discovery
    return [_serialize_pending(item) for item in discovery.get_pending_devices()]


@router.post("/scan")
async def start_discovery_scan(request: Request) -> Dict[str, Any]:
    """Start a thorough global IoT scan (SSDP + mDNS + UDP)."""
    discovery = request.app.state.discovery
    return await discovery.start_active_scan()


@router.post("/scan/stop")
async def stop_discovery_scan(request: Request) -> Dict[str, Any]:
    """Stop the active discovery scan."""
    discovery = request.app.state.discovery
    return await discovery.stop_active_scan()


@router.post("/register/{device_id}")
async def register_discovered_device(
    request: Request,
    device_id: str,
    body: RegisterDiscoveryRequest,
) -> Dict[str, Any]:
    """Promote a discovered device into the hub registry."""
    discovery = request.app.state.discovery
    registry = request.app.state.registry
    pending = discovery.pop_pending_device(device_id)

    if not pending:
        raise HTTPException(status_code=404, detail="Discovered device not found")

    manufacturer_key = pending.get("manufacturer", "unknown")
    device_type = pending.get("device_type", "unknown")
    ip = pending.get("ip_address", "")
    name = body.name or pending.get("name") or device_id
    room = body.room or "Unassigned"
    stream_url = pending.get("stream_url")
    if device_type == "camera" and ip and not stream_url:
        stream_url = f"rtsp://{ip}:554/live"

    # ── VALIDATION GATE ──  NEW: require 3-gate validation before promotion
    async for session in get_db_session():
        from sqlalchemy import select
        from models.database import DiscoveryCandidate
        from services.validation import MIN_TRUST_FOR_CONTROL

        result = await session.execute(
            select(DiscoveryCandidate).where(DiscoveryCandidate.id == device_id)
        )
        candidate = result.scalar_one_or_none()

        if candidate is None:
            # No DB candidate found — device was discovered in-memory only.
            # Persist it first so validation can run on it.
            candidate = DiscoveryCandidate(
                id=device_id,
                source_scanner=pending.get("source_scanner", "unknown"),
                priority=50,
                ip_address=ip,
                port=pending.get("port"),
                mac_address=pending.get("mac_address"),
                proposed_protocol=pending.get("protocol", "SSDP"),
                proposed_name=name,
                validation_status="pending",
                trust_score=0,
                discovered_at=time.time(),
                last_probed_at=time.time(),
            )
            session.add(candidate)
            await session.commit()
            raise HTTPException(
                status_code=403,
                detail="Device must be validated before registration. "
                       f"POST /api/validation/validate/{device_id} first.",
            )

        if candidate.validation_status != "verified":
            raise HTTPException(
                status_code=403,
                detail=f"Device validation status is '{candidate.validation_status}'. "
                       f"Run POST /api/validation/validate/{device_id} first.",
            )

        if candidate.trust_score < MIN_TRUST_FOR_CONTROL:
            raise HTTPException(
                status_code=403,
                detail=f"Trust score {candidate.trust_score} is below minimum {MIN_TRUST_FOR_CONTROL}. "
                       f"Re-run validation or investigate why the device failed gates.",
            )

        break  # session consumed by the for-loop

    device_state = DeviceState(
        device_id=device_id,
        manufacturer=_display_manufacturer(manufacturer_key),
        model=pending.get("model", "unknown"),
        device_type=device_type,
        online=True,
        state={
            "name": name,
            "room": room,
            "power": True,
            "ip": ip,
            "ip_address": ip,
            "protocol": pending.get("protocol", "SSDP"),
            "signal_strength": pending.get("signal_strength", 70),
            "stream_url": stream_url,
            "firmware": pending.get("firmware", "unknown"),
        },
        last_updated=time.time(),
    )
    await registry.update(device_id, device_state)

    device_config = None
    try:
        async for session in get_db_session():
            device_config = DeviceConfig(
                device_id=device_id,
                manufacturer=manufacturer_key,
                model=pending.get("model", "unknown"),
                device_type=device_type,
                ip_address=ip or None,
                protocol=pending.get("protocol", "SSDP"),
                room=room,
                name=name,
                enabled=True,
            )
            session.add(device_config)
            await session.commit()
            await log_event(
                session,
                event_type="discovery",
                device_id=device_id,
                manufacturer=manufacturer_key,
                details={"ip": ip, "protocol": pending.get("protocol")},
            )
            break
    except Exception as exc:
        logger.warning("Failed to persist discovered device: %s", exc)

    if device_config is not None:
        try:
            manager = request.app.state.device_manager
            await manager.add_device(device_config)
        except Exception as exc:
            logger.warning("Failed to attach driver for %s: %s", device_id, exc)

    return {"success": True, "device_id": device_id, "name": name}