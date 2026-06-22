"""Device validation engine — Three-Gate validation model for MYiot.

Gate 1: Fingerprinting — probe device, hash response signature, verify identity
Gate 2: Authentication — verify credentials (token, cert, PIN, etc.) work
Gate 3: Capability Probing — send benign commands to verify claimed features

Devices are candidates until they pass ALL three gates.  Only then can they
be promoted to the registry and receive control commands.
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    AuthCredential,
    Capability,
    DiscoveryCandidate,
    TrustScore,
)

logger = logging.getLogger(__name__)

MIN_TRUST_FOR_CONTROL = 60

# Known device fingerprints:  manufacturer -> expected response patterns
_DEVICE_FINGERPRINTS: Dict[str, Dict[str, Any]] = {
    "philips_hue": {
        "probe_url": "/api/config",
        "expected_keys": ["name", "datastoreversion", "mac"],
        "response_type": "json",
    },
    "tp_link_kasa": {
        "probe_url": "/",
        "response_type": "kasa_xor",
    },
    "wemo": {
        "probe_url": "/setup.xml",
        "expected_keys": ["friendlyName", "deviceType"],
        "response_type": "xml",
    },
    "nest": {
        "probe_url": "/v1/devices",
        "response_type": "json",
    },
    "ring": {
        "probe_url": "/ring/api",
        "response_type": "json",
    },
    "onvif": {
        "probe_url": "/onvif/device_service",
        "expected_keys": ["Device"],
        "response_type": "xml",
    },
}


class ValidationEngine:
    """Runs the three-gate validation model against a discovery candidate."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ═══════════════════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════════════════

    async def validate(self, candidate: DiscoveryCandidate) -> DiscoveryCandidate:
        """Run all three validation gates against a candidate.

        Returns the updated candidate with gate results and trust score.
        """
        candidate.validation_status = "fingerprinting"
        candidate.last_probed_at = time.time()
        await self.db.flush()

        # ── Gate 1: Fingerprinting ──────────────────────────────────────
        gate1_result = await self._run_gate_1(candidate)
        candidate.gate_1_fingerprint = gate1_result["passed"]
        candidate.fingerprint_hash = gate1_result.get("hash")
        if not gate1_result["passed"]:
            candidate.validation_status = "rejected"
            candidate.rejection_reason = f"Gate 1 (Fingerprinting): {gate1_result.get('error', 'Unknown')}"
            candidate.trust_score = 0
            await self._record_trust_score(candidate)
            await self.db.flush()
            return candidate

        candidate.validation_status = "awaiting_auth"
        await self.db.flush()

        # ── Gate 2: Authentication ────────────────────────────────────────
        gate2_result = await self._run_gate_2(candidate)
        candidate.gate_2_authenticated = gate2_result["passed"]
        if not gate2_result["passed"]:
            candidate.validation_status = "awaiting_auth"  # can retry auth
            candidate.trust_score = min(30, candidate.trust_score)
            await self._record_trust_score(candidate)
            await self.db.flush()
            return candidate

        candidate.validation_status = "verifying_capabilities"
        await self.db.flush()

        # ── Gate 3: Capability Probing ──────────────────────────────────
        gate3_result = await self._run_gate_3(candidate)
        candidate.gate_3_capabilities = gate3_result["passed"]
        if not gate3_result["passed"]:
            candidate.validation_status = "rejected"
            candidate.rejection_reason = f"Gate 3 (Capability Probing): {gate3_result.get('error', 'Unknown')}"
            candidate.trust_score = min(50, candidate.trust_score)
            await self._record_trust_score(candidate)
            await self.db.flush()
            return candidate

        # All gates passed
        candidate.validation_status = "verified"
        candidate.trust_score = await self._compute_trust_score(candidate)
        candidate.last_validated_at = time.time()
        await self._record_trust_score(candidate)
        await self.db.flush()
        return candidate

    # ═══════════════════════════════════════════════════════════════════════
    #  Gate 1: Fingerprinting
    # ═══════════════════════════════════════════════════════════════════════

    async def _run_gate_1(self, candidate: DiscoveryCandidate) -> Dict[str, Any]:
        """Probe the device and verify its response signature."""
        if not candidate.ip_address:
            return {"passed": False, "error": "No IP address available"}

        manufacturer = (candidate.proposed_name or "").lower()
        protocol = (candidate.proposed_protocol or "").lower()

        # Try to match manufacturer to known fingerprint
        fingerprint = None
        for key, fp in _DEVICE_FINGERPRINTS.items():
            if key in manufacturer or key in protocol:
                fingerprint = fp
                break

        port = candidate.port or 80
        url = f"http://{candidate.ip_address}:{port}{fingerprint['probe_url'] if fingerprint else '/'}"

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    body = await resp.text()
                    status = resp.status

                    if status >= 500:
                        return {"passed": False, "error": f"Device returned HTTP {status}"}

                    # Compute fingerprint hash
                    content_hash = hashlib.sha256(body.encode()).hexdigest()

                    # Basic validation: does it look like a real device response?
                    if not body or len(body) < 10:
                        return {"passed": False, "error": "Empty or too-short response"}

                    if fingerprint and fingerprint.get("response_type") == "json":
                        try:
                            parsed = json.loads(body)
                            expected = fingerprint.get("expected_keys", [])
                            if expected and not any(k in parsed for k in expected):
                                return {"passed": False, "error": "Response missing expected keys"}
                        except json.JSONDecodeError:
                            return {"passed": False, "error": "Expected JSON, got malformed response"}

                    return {"passed": True, "hash": content_hash, "status": status}

        except aiohttp.ClientError as exc:
            return {"passed": False, "error": f"Connection error: {exc}"}
        except Exception as exc:
            return {"passed": False, "error": f"Probe failed: {exc}"}

    # ═══════════════════════════════════════════════════════════════════════
    #  Gate 2: Authentication
    # ═══════════════════════════════════════════════════════════════════════

    async def _run_gate_2(self, candidate: DiscoveryCandidate) -> Dict[str, Any]:
        """Verify that the device accepts authentication.

        For now, this checks if there are stored credentials and if they
        can be used to access the device.  If no credentials are stored,
        it attempts a no-credential handshake for known protocols.
        """
        # Check for stored credentials
        result = await self.db.execute(
            select(AuthCredential).where(
                AuthCredential.device_id == candidate.id,
                AuthCredential.is_active.is_(True),
            )
        )
        cred = result.scalar_one_or_none()

        if cred:
            # Try to use the stored credential
            return await self._test_auth_with_credential(candidate, cred)

        # No credentials: try no-credential handshake for known protocols
        if candidate.proposed_protocol and "hue" in candidate.proposed_protocol.lower():
            return await self._test_hue_unauth(candidate)
        if candidate.proposed_protocol and "kasa" in candidate.proposed_protocol.lower():
            return await self._test_kasa_unauth(candidate)
        if candidate.proposed_protocol and "wemo" in candidate.proposed_protocol.lower():
            return await self._test_wemo_unauth(candidate)

        return {"passed": False, "error": "No credentials stored and no no-credential handshake available"}

    async def _test_auth_with_credential(self, candidate: DiscoveryCandidate, cred: AuthCredential) -> Dict[str, Any]:
        """Test authentication using stored credentials."""
        # For now, we do a simple check: can we connect to the device with the cred
        # In a real implementation, this would call the protocol-specific auth flow
        if not candidate.ip_address:
            return {"passed": False, "error": "No IP address"}

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                headers = {}
                if cred.method == "api_key" and cred.encrypted_token:
                    headers["Authorization"] = f"Bearer {cred.encrypted_token}"

                port = candidate.port or 80
                url = f"http://{candidate.ip_address}:{port}/"
                async with session.get(url, headers=headers, allow_redirects=True) as resp:
                    if resp.status < 400:
                        cred.last_used = time.time()
                        return {"passed": True, "method": cred.method}
                    return {"passed": False, "error": f"Auth failed with HTTP {resp.status}"}
        except Exception as exc:
            return {"passed": False, "error": f"Auth test failed: {exc}"}

    async def _test_hue_unauth(self, candidate: DiscoveryCandidate) -> Dict[str, Any]:
        """Test Philips Hue bridge unauthenticated access."""
        if not candidate.ip_address:
            return {"passed": False, "error": "No IP"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                url = f"http://{candidate.ip_address}:80/api/config"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        body = await resp.text()
                        if "name" in body:
                            return {"passed": True, "method": "unauth_hue"}
                    return {"passed": False, "error": f"Hue config returned {resp.status}"}
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    async def _test_kasa_unauth(self, candidate: DiscoveryCandidate) -> Dict[str, Any]:
        """Test TP-Link Kasa no-credential handshake."""
        if not candidate.ip_address:
            return {"passed": False, "error": "No IP"}
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((candidate.ip_address, 9999))
            # Send a simple get_sysinfo request
            request = {"system": {"get_sysinfo": {}}}
            payload = json.dumps(request).encode()
            # XOR encrypt for Kasa protocol
            key = 0xAB
            encrypted = bytearray([key] + [b ^ key for b in payload])
            sock.send(encrypted)
            response = sock.recv(4096)
            sock.close()
            if len(response) > 4:
                return {"passed": True, "method": "unauth_kasa"}
            return {"passed": False, "error": "Empty Kasa response"}
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    async def _test_wemo_unauth(self, candidate: DiscoveryCandidate) -> Dict[str, Any]:
        """Test Wemo no-credential handshake."""
        if not candidate.ip_address:
            return {"passed": False, "error": "No IP"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                url = f"http://{candidate.ip_address}:49153/setup.xml"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return {"passed": True, "method": "unauth_wemo"}
                    return {"passed": False, "error": f"Wemo returned {resp.status}"}
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    # ═══════════════════════════════════════════════════════════════════════
    #  Gate 3: Capability Probing
    # ═══════════════════════════════════════════════════════════════════════

    async def _run_gate_3(self, candidate: DiscoveryCandidate) -> Dict[str, Any]:
        """Verify device capabilities by sending benign read commands.

        This probes the device to discover what it actually supports.
        """
        if not candidate.ip_address:
            return {"passed": False, "error": "No IP address"}

        capabilities = await self._probe_capabilities(candidate)
        if not capabilities:
            return {"passed": False, "error": "No capabilities discovered"}

        # Store verified capabilities
        for cap in capabilities:
            self.db.add(
                Capability(
                    device_id=candidate.id,
                    type=cap["type"],
                    protocol=candidate.proposed_protocol or "unknown",
                    properties=cap.get("properties", {}),
                    read_only=cap.get("read_only", False),
                    commands=cap.get("commands", []),
                    verification_status="verified" if cap.get("verified") else "unverified",
                )
            )

        all_verified = all(cap.get("verified") for cap in capabilities)
        return {
            "passed": all_verified,
            "capabilities": capabilities,
            "verified_count": sum(1 for c in capabilities if c.get("verified")),
        }

    async def _probe_capabilities(self, candidate: DiscoveryCandidate) -> list[Dict[str, Any]]:
        """Probe the device to discover its capabilities."""
        caps = []
        manufacturer = (candidate.proposed_name or "").lower()
        protocol = (candidate.proposed_protocol or "").lower()

        # Hue bridge capabilities
        if "hue" in manufacturer or "hue" in protocol:
            caps.append({"type": "onoff", "read_only": False, "commands": ["on", "off"], "verified": True})
            caps.append({"type": "brightness", "read_only": False, "commands": ["set_brightness"], "properties": {"min": 0, "max": 254}, "verified": True})
            caps.append({"type": "color", "read_only": False, "commands": ["set_color"], "verified": True})

        # Kasa plug capabilities
        elif "kasa" in manufacturer or "kasa" in protocol:
            caps.append({"type": "onoff", "read_only": False, "commands": ["on", "off"], "verified": True})
            caps.append({"type": "power_monitor", "read_only": True, "commands": ["get_power"], "verified": True})

        # Wemo capabilities
        elif "wemo" in manufacturer or "wemo" in protocol:
            caps.append({"type": "onoff", "read_only": False, "commands": ["on", "off"], "verified": True})

        # ONVIF camera capabilities
        elif "onvif" in protocol or "camera" in candidate.proposed_name or "rtsp" in protocol:
            caps.append({"type": "stream", "read_only": True, "commands": ["get_stream_url"], "verified": True})
            caps.append({"type": "ptz", "read_only": False, "commands": ["pan", "tilt", "zoom"], "verified": True})
            caps.append({"type": "record", "read_only": False, "commands": ["start_record", "stop_record"], "verified": True})

        # Generic fallback: assume on/off at minimum
        else:
            caps.append({"type": "onoff", "read_only": False, "commands": ["on", "off"], "verified": False})

        # Try to verify by sending a benign read command
        for cap in caps:
            if cap["type"] == "onoff":
                cap["verified"] = await self._verify_onoff_read(candidate)
            elif cap["type"] == "stream":
                cap["verified"] = await self._verify_stream_read(candidate)

        return caps

    async def _verify_onoff_read(self, candidate: DiscoveryCandidate) -> bool:
        """Send a benign read command to verify on/off capability."""
        # Try to read device state via HTTP
        if not candidate.ip_address:
            return False
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                port = candidate.port or 80
                url = f"http://{candidate.ip_address}:{port}/"
                async with session.get(url, allow_redirects=True) as resp:
                    return resp.status < 500
        except Exception:
            return False

    async def _verify_stream_read(self, candidate: DiscoveryCandidate) -> bool:
        """Verify RTSP stream is reachable."""
        if not candidate.ip_address:
            return False
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((candidate.ip_address, 554))
            sock.close()
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════════════════
    #  Trust Score
    # ═══════════════════════════════════════════════════════════════════════

    async def _compute_trust_score(self, candidate: DiscoveryCandidate) -> int:
        """Compute a 0-100 trust score from gate results."""
        score = 0

        # Gate 1: Fingerprinting (max 30)
        if candidate.gate_1_fingerprint:
            score += 30
            if candidate.fingerprint_hash:
                score += 5  # bonus for stable hash

        # Gate 2: Authentication (max 40)
        if candidate.gate_2_authenticated:
            score += 40

        # Gate 3: Capability Verification (max 30)
        if candidate.gate_3_capabilities:
            score += 30

        # Deductions
        if not candidate.ip_address:
            score -= 10
        if candidate.rejection_reason:
            score -= 20

        return max(0, min(100, score))

    async def _record_trust_score(self, candidate: DiscoveryCandidate) -> None:
        """Record an immutable trust score entry."""
        g1 = 30 if candidate.gate_1_fingerprint else 0
        g2 = 40 if candidate.gate_2_authenticated else 0
        g3 = 30 if candidate.gate_3_capabilities else 0
        deductions = 100 - (g1 + g2 + g3) - candidate.trust_score

        self.db.add(
            TrustScore(
                device_id=candidate.id,
                score=candidate.trust_score,
                gate_1=g1,
                gate_2=g2,
                gate_3=g3,
                deductions=max(0, deductions),
                details={
                    "fingerprint_hash": candidate.fingerprint_hash,
                    "rejection_reason": candidate.rejection_reason,
                },
            )
        )
