"""Tests for the device validation engine (three-gate model) integrated into MYiot."""

import time
import uuid

import pytest
from sqlalchemy import delete

from main import app  # noqa: E402
from models.database import (
    DiscoveryCandidate,
    TrustScore,
    get_async_session_factory,
    init_db,
)


@pytest.fixture(autouse=True)
async def setup_validation_tables():
    """Ensure all DB tables exist before each validation test."""
    await init_db()
    yield
    factory = get_async_session_factory()
    async with factory() as session:
        await session.execute(delete(TrustScore))
        await session.execute(delete(DiscoveryCandidate))
        await session.commit()


@pytest.fixture
def client():
    """Provide a FastAPI TestClient for the MYiot test app."""
    from fastapi.testclient import TestClient

    with TestClient(app) as tc:
        yield tc


async def _create_test_candidate(
    session,
    candidate_id: str = None,
    ip: str = "192.168.1.100",
    status: str = "pending",
    trust_score: int = 0,
    gate1: bool = False,
    gate2: bool = False,
    gate3: bool = False,
) -> DiscoveryCandidate:
    """Helper to create a test candidate in the DB."""
    candidate = DiscoveryCandidate(
        id=candidate_id or str(uuid.uuid4()),
        source_scanner="test_scanner",
        priority=10,
        ip_address=ip,
        port=80,
        mac_address="AA:BB:CC:DD:EE:01",
        proposed_protocol="hue",
        proposed_name="Test Bulb",
        validation_status=status,
        trust_score=trust_score,
        gate_1_fingerprint=gate1,
        gate_2_authenticated=gate2,
        gate_3_capabilities=gate3,
        discovered_at=time.time(),
        last_probed_at=time.time(),
    )
    session.add(candidate)
    await session.commit()
    return candidate


@pytest.mark.asyncio
async def test_validation_api_returns_404_for_unknown_candidate(client):
    """GET /api/validation/status/{id} should 404 for non-existent candidates."""
    resp = client.get("/api/validation/status/nonexistent-id")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Candidate not found"


@pytest.mark.asyncio
async def test_validation_api_shows_pending_status(client):
    """GET /api/validation/status should return pending for new candidates."""
    factory = get_async_session_factory()
    async with factory() as session:
        candidate = await _create_test_candidate(session, status="pending")

    resp = client.get(f"/api/validation/status/{candidate.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["validation_status"] == "pending"
    assert data["trust_score"] == 0
    assert data["gates"]["fingerprint"] is False
    assert data["gates"]["authenticated"] is False
    assert data["gates"]["capabilities"] is False
    assert data["can_control"] is False


@pytest.mark.asyncio
async def test_validation_api_blocks_registration_for_unverified(client):
    """POST /api/discovery/register/{id} should 403 for unverified candidates."""
    factory = get_async_session_factory()
    async with factory() as session:
        candidate = await _create_test_candidate(
            session,
            status="pending",
            trust_score=0,
        )

    # Add to the discovery listener's pending dict so registration can find it
    app.state.discovery._pending[candidate.id] = {
        "id": candidate.id,
        "device_id": candidate.id,
        "name": candidate.proposed_name,
        "manufacturer": candidate.proposed_protocol,
        "device_type": "light",
        "ip_address": candidate.ip_address,
        "protocol": candidate.proposed_protocol,
        "mac_address": candidate.mac_address,
        "model": "Test",
        "signal_strength": 80,
        "scan_phase": "complete",
        "discovered_at": time.time(),
        "last_seen": time.time(),
    }

    # Register endpoint should require validation first
    resp = client.post(
        f"/api/discovery/register/{candidate.id}",
        json={"name": "Test", "room": "Office"},
    )
    assert resp.status_code == 403
    assert "validation" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_validation_api_blocks_registration_for_low_trust(client):
    """POST /api/discovery/register/{id} should 403 for trust_score < 60."""
    factory = get_async_session_factory()
    async with factory() as session:
        candidate = await _create_test_candidate(
            session,
            status="verified",
            trust_score=30,  # below MIN_TRUST_FOR_CONTROL
            gate1=True,
            gate2=False,
            gate3=True,
        )

    # Add to the discovery listener's pending dict so registration can find it
    app.state.discovery._pending[candidate.id] = {
        "id": candidate.id,
        "device_id": candidate.id,
        "name": candidate.proposed_name,
        "manufacturer": candidate.proposed_protocol,
        "device_type": "light",
        "ip_address": candidate.ip_address,
        "protocol": candidate.proposed_protocol,
        "mac_address": candidate.mac_address,
        "model": "Test",
        "signal_strength": 80,
        "scan_phase": "complete",
        "discovered_at": time.time(),
        "last_seen": time.time(),
    }

    resp = client.post(
        f"/api/discovery/register/{candidate.id}",
        json={"name": "Test", "room": "Office"},
    )
    assert resp.status_code == 403
    assert "trust score" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_validation_api_allows_registration_for_high_trust(client):
    """POST /api/discovery/register/{id} should succeed for verified + high trust."""
    factory = get_async_session_factory()
    async with factory() as session:
        candidate = await _create_test_candidate(
            session,
            status="verified",
            trust_score=95,
            gate1=True,
            gate2=True,
            gate3=True,
        )

    # The discovery listener must have this in its pending dict for registration
    # to work (since the existing code pops from _pending).  We add it there.
    listener = app.state.discovery
    listener._pending[candidate.id] = {
        "id": candidate.id,
        "device_id": candidate.id,
        "name": candidate.proposed_name,
        "manufacturer": candidate.proposed_protocol,
        "device_type": "light",
        "ip_address": candidate.ip_address,
        "protocol": candidate.proposed_protocol,
        "mac_address": candidate.mac_address,
        "model": "Test",
        "signal_strength": 80,
        "scan_phase": "complete",
        "discovered_at": time.time(),
        "last_seen": time.time(),
    }

    resp = client.post(
        f"/api/discovery/register/{candidate.id}",
        json={"name": "Test Bulb", "room": "Office"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["device_id"] == candidate.id


@pytest.mark.asyncio
async def test_trust_score_history_endpoint(client):
    """GET /api/validation/trust/{device_id} should return trust score history."""
    factory = get_async_session_factory()
    async with factory() as session:
        candidate = await _create_test_candidate(
            session,
            status="verified",
            trust_score=85,
            gate1=True,
            gate2=True,
            gate3=True,
        )
        # Record a trust score entry
        session.add(
            TrustScore(
                device_id=candidate.id,
                score=85,
                gate_1=30,
                gate_2=40,
                gate_3=15,
                deductions=0,
                details={"test": True},
            )
        )
        await session.commit()

    resp = client.get(f"/api/validation/trust/{candidate.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["score"] == 85
    assert data[0]["gate_1"] == 30
    assert data[0]["gate_2"] == 40


@pytest.mark.asyncio
async def test_validate_endpoint_runs_for_pending_candidate(client):
    """POST /api/validation/validate/{id} should run validation on a pending candidate."""
    factory = get_async_session_factory()
    async with factory() as session:
        candidate = await _create_test_candidate(
            session,
            ip="192.168.1.200",  # non-routable IP so gate 1 will fail
            status="pending",
        )

    resp = client.post(f"/api/validation/validate/{candidate.id}", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate_id"] == candidate.id
    # Since the IP is non-routable, fingerprinting should fail
    assert data["status"] in ("rejected", "awaiting_auth")
    assert data["gates"]["fingerprint"] is not None  # bool or None
    assert "trust_score" in data
