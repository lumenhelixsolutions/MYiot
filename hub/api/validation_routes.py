"""REST API routes for device validation and trust scoring.

Endpoints:
    POST /api/validation/validate/{candidate_id}  — Run 3-gate validation
    GET  /api/validation/status/{candidate_id}    — Get validation status
    POST /api/validation/revalidate/{device_id}   — Re-validate a registered device
    GET  /api/validation/trust/{device_id}        — Get trust score history
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import desc, select

from models.database import (
    Capability,
    DiscoveryCandidate,
    TrustScore,
    get_db_session,
)
from services.validation import MIN_TRUST_FOR_CONTROL, ValidationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/validation", tags=["validation"])


class ValidateRequest(BaseModel):
    """Request to validate a discovered candidate."""
    force: bool = False  # Re-run even if already verified


class TrustScoreResponse(BaseModel):
    score: int
    gate_1: int
    gate_2: int
    gate_3: int
    deductions: int
    status: str
    can_control: bool


@router.post("/validate/{candidate_id}")
async def validate_candidate(
    request: Request, candidate_id: str, body: ValidateRequest
) -> Dict[str, Any]:
    """Run the three-gate validation model on a discovery candidate.

    Gate 1: Fingerprinting — probe device and verify response signature
    Gate 2: Authentication — verify credentials work
    Gate 3: Capability Probing — verify claimed features respond to commands

    Only candidates with trust_score >= 60 can be promoted to the registry.
    """
    async for session in get_db_session():
        result = await session.execute(
            select(DiscoveryCandidate).where(DiscoveryCandidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        if candidate.validation_status == "verified" and not body.force:
            return {
                "candidate_id": candidate_id,
                "status": candidate.validation_status,
                "trust_score": candidate.trust_score,
                "gates": {
                    "fingerprint": candidate.gate_1_fingerprint,
                    "authenticated": candidate.gate_2_authenticated,
                    "capabilities": candidate.gate_3_capabilities,
                },
                "already_verified": True,
            }

        engine = ValidationEngine(session)
        validated = await engine.validate(candidate)
        await session.commit()

        return {
            "candidate_id": candidate_id,
            "status": validated.validation_status,
            "trust_score": validated.trust_score,
            "gates": {
                "fingerprint": validated.gate_1_fingerprint,
                "authenticated": validated.gate_2_authenticated,
                "capabilities": validated.gate_3_capabilities,
            },
            "can_control": validated.trust_score >= MIN_TRUST_FOR_CONTROL,
            "rejection_reason": validated.rejection_reason,
        }


@router.get("/status/{candidate_id}")
async def get_validation_status(request: Request, candidate_id: str) -> Dict[str, Any]:
    """Get the current validation status of a discovery candidate."""
    async for session in get_db_session():
        result = await session.execute(
            select(DiscoveryCandidate).where(DiscoveryCandidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Count verified capabilities
        cap_result = await session.execute(
            select(Capability).where(Capability.device_id == candidate_id)
        )
        capabilities = cap_result.scalars().all()

        return {
            "candidate_id": candidate_id,
            "validation_status": candidate.validation_status,
            "trust_score": candidate.trust_score,
            "gates": {
                "fingerprint": candidate.gate_1_fingerprint,
                "authenticated": candidate.gate_2_authenticated,
                "capabilities": candidate.gate_3_capabilities,
            },
            "can_control": candidate.trust_score >= MIN_TRUST_FOR_CONTROL,
            "rejection_reason": candidate.rejection_reason,
            "fingerprint_hash": candidate.fingerprint_hash,
            "discovered_at": candidate.discovered_at,
            "last_validated_at": candidate.last_validated_at,
            "capabilities": [c.to_dict() for c in capabilities],
        }


@router.post("/revalidate/{device_id}")
async def revalidate_device(request: Request, device_id: str) -> Dict[str, Any]:
    """Re-validate a device that is already in the registry.

    This runs all three gates again and updates the trust score.
    If trust_score drops below 60, the device is marked as degraded.
    """
    registry = request.app.state.registry

    # Find the device in the registry
    device = await registry.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found in registry")

    async for session in get_db_session():
        # Find the candidate that was promoted to this device
        result = await session.execute(
            select(DiscoveryCandidate).where(DiscoveryCandidate.device_id == device_id)
        )
        candidate = result.scalar_one_or_none()

        if not candidate:
            # Device was manually added, create a synthetic candidate
            from uuid import uuid4
            candidate = DiscoveryCandidate(
                id=str(uuid4()),
                source_scanner="manual",
                priority=50,
                ip_address=device.state.get("ip_address"),
                proposed_protocol=device.state.get("protocol", "unknown"),
                proposed_name=device.manufacturer,
                validation_status="pending",
                trust_score=0,
                discovered_at=device.last_updated,
                device_id=device_id,
            )
            session.add(candidate)
            await session.flush()

        engine = ValidationEngine(session)
        validated = await engine.validate(candidate)
        await session.commit()

        # Update registry device status based on trust score
        if validated.trust_score < MIN_TRUST_FOR_CONTROL:
            device.online = False
            device.state["trust_status"] = "degraded"
            device.state["validation_status"] = validated.validation_status
            await registry.update(device_id, device)

        return {
            "device_id": device_id,
            "status": validated.validation_status,
            "trust_score": validated.trust_score,
            "gates": {
                "fingerprint": validated.gate_1_fingerprint,
                "authenticated": validated.gate_2_authenticated,
                "capabilities": validated.gate_3_capabilities,
            },
            "can_control": validated.trust_score >= MIN_TRUST_FOR_CONTROL,
        }


@router.get("/trust/{device_id}")
async def get_trust_history(request: Request, device_id: str) -> List[Dict[str, Any]]:
    """Get the trust score history for a device."""
    async for session in get_db_session():
        result = await session.execute(
            select(TrustScore)
            .where(TrustScore.device_id == device_id)
            .order_by(desc(TrustScore.computed_at))
        )
        scores = result.scalars().all()
        return [s.to_dict() for s in scores]
