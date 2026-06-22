"""
SQLAlchemy database models for Smart Home Universal Hub.

Defines the DeviceConfig and EventLog models for SQLite persistence,
along with async engine setup using aiosqlite and session management
utilities.
"""

import logging
import os
import time
from typing import AsyncGenerator, Optional

from sqlalchemy import (
    ForeignKey,
    JSON,
    Boolean,
    Column,
    Float,
    Integer,
    String,
    desc,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Use async SQLite engine
ASYNC_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite+aiosqlite:///./data/hub.db"
)
SYNC_DATABASE_URL = os.environ.get("SYNC_DATABASE_URL", "sqlite:///./data/hub.db")

Base = declarative_base()


class DeviceConfig(Base):
    """
    Device configuration model.

    Stores persistent configuration for each connected smart home device
    including network details, authentication, and custom mappings.
    """

    __tablename__ = "devices"

    device_id = Column(String, primary_key=True)
    manufacturer = Column(String, nullable=False)
    model = Column(String, nullable=True)
    device_type = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    port = Column(Integer, nullable=True)
    protocol = Column(String, nullable=True)
    auth_type = Column(String, nullable=True)
    credentials_key = Column(String, nullable=True)
    custom_map = Column(JSON, nullable=True)
    room = Column(String, nullable=True)
    name = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    last_state = Column(JSON, nullable=True)
    last_seen_at = Column(Float, nullable=True)

    def to_dict(self) -> dict:
        """Serialize the device config to a dictionary."""
        return {
            "device_id": self.device_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "device_type": self.device_type,
            "ip_address": self.ip_address,
            "port": self.port,
            "protocol": self.protocol,
            "auth_type": self.auth_type,
            "credentials_key": self.credentials_key,
            "custom_map": self.custom_map,
            "room": self.room,
            "name": self.name,
            "enabled": self.enabled,
            "last_state": self.last_state,
            "last_seen_at": self.last_seen_at,
        }

    def __repr__(self) -> str:
        return (
            f"<DeviceConfig(device_id='{self.device_id}', "
            f"manufacturer='{self.manufacturer}', "
            f"device_type='{self.device_type}', "
            f"enabled={self.enabled})>"
        )


class EventLog(Base):
    """
    Event log model.

    Records all significant events in the system including device discovery,
    state changes, commands, and errors for audit and debugging purposes.
    """

    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False)
    event_type = Column(String, nullable=False)
    device_id = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    details = Column(JSON, nullable=True)

    def to_dict(self) -> dict:
        """Serialize the event log entry to a dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "device_id": self.device_id,
            "manufacturer": self.manufacturer,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return (
            f"<EventLog(id={self.id}, event_type='{self.event_type}', "
            f"device_id='{self.device_id}', "
            f"timestamp={self.timestamp})>"
        )


class User(Base):
    """Admin user account."""

    __tablename__ = "users"

    username = Column(String, primary_key=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="admin")
    created_at = Column(Float, nullable=False, default=time.time)
    updated_at = Column(Float, nullable=False, default=time.time, onupdate=time.time)

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _migrate_db(sync_conn) -> None:
    """Add columns introduced after the initial schema creation."""
    from sqlalchemy import inspect

    inspector = inspect(sync_conn)
    columns = {col["name"] for col in inspector.get_columns("devices")}

    if "last_state" not in columns:
        sync_conn.execute(text("ALTER TABLE devices ADD COLUMN last_state JSON"))
    if "last_seen_at" not in columns:
        sync_conn.execute(text("ALTER TABLE devices ADD COLUMN last_seen_at FLOAT"))


# --- Async engine and session setup ---

_async_engine: Optional[object] = None
_async_session_factory = None


def get_async_engine():
    """Get or create the async database engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            ASYNC_DATABASE_URL,
            echo=False,
            future=True,
        )
    return _async_engine


def get_async_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def init_db() -> None:
    """
    Initialize the database by creating all tables.

    Should be called once during application startup.
    """
    os.makedirs("./data", exist_ok=True)
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_db)
    logger.info("Database initialized — tables created")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for FastAPI to provide database sessions.

    Yields an async session and ensures proper cleanup after the request.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def log_event(
    session: AsyncSession,
    event_type: str,
    device_id: Optional[str] = None,
    manufacturer: Optional[str] = None,
    details: Optional[dict] = None,
) -> EventLog:
    """
    Log an event to the database.

    Args:
        session: Active async database session.
        event_type: Type of event ("discovery", "state_change", "command", "error").
        device_id: Optional device identifier.
        manufacturer: Optional manufacturer name.
        details: Optional dictionary with additional event details.

    Returns:
        The created EventLog instance.
    """
    event = EventLog(
        timestamp=time.time(),
        event_type=event_type,
        device_id=device_id,
        manufacturer=manufacturer,
        details=details or {},
    )
    session.add(event)
    await session.commit()
    return event


async def get_recent_logs(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
    event_type: Optional[str] = None,
    device_id: Optional[str] = None,
) -> list[EventLog]:
    """
    Retrieve recent event log entries with optional filtering.

    Args:
        session: Active async database session.
        limit: Maximum number of entries to return.
        offset: Number of entries to skip (for pagination).
        event_type: Optional filter by event type.
        device_id: Optional filter by device ID.

    Returns:
        List of EventLog entries ordered by most recent first.
    """
    query = select(EventLog).order_by(desc(EventLog.timestamp))

    if event_type:
        query = query.where(EventLog.event_type == event_type)
    if device_id:
        query = query.where(EventLog.device_id == device_id)

    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_device_config(
    session: AsyncSession, device_id: str
) -> Optional[DeviceConfig]:
    """
    Retrieve a device configuration by ID.

    Args:
        session: Active async database session.
        device_id: Unique device identifier.

    Returns:
        DeviceConfig if found, None otherwise.
    """
    result = await session.execute(
        select(DeviceConfig).where(DeviceConfig.device_id == device_id)
    )
    return result.scalar_one_or_none()


async def get_all_device_configs(
    session: AsyncSession, device_type: Optional[str] = None
) -> list[DeviceConfig]:
    """
    Retrieve all device configurations with optional filtering.

    Args:
        session: Active async database session.
        device_type: Optional filter by device type.

    Returns:
        List of DeviceConfig entries.
    """
    query = select(DeviceConfig)
    if device_type:
        query = query.where(DeviceConfig.device_type == device_type)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_device_state(
    session: AsyncSession, device_id: str, state: dict
) -> None:
    """Update the persisted last_state and last_seen_at for a device.

    If no configuration row exists for the device, one is created using the
    manufacturer, model, and device_type fields when present in ``state``.

    Note:
        This helper does **not** commit the session. Callers are responsible for
        committing or rolling back the transaction.
    """
    result = await session.execute(
        select(DeviceConfig).where(DeviceConfig.device_id == device_id)
    )
    db_device = result.scalar_one_or_none()
    if db_device:
        db_device.last_state = state
        db_device.last_seen_at = time.time()
    else:
        db_device = DeviceConfig(
            device_id=device_id,
            manufacturer=state.get("manufacturer", "unknown"),
            model=state.get("model"),
            device_type=state.get("device_type", "unknown"),
            last_state=state,
            last_seen_at=time.time(),
        )
        session.add(db_device)


# ═══════════════════════════════════════════════════════════════════════════════
#  NEW: Validation & Trust-Score Models (integrated into existing MYiot hub)
# ═══════════════════════════════════════════════════════════════════════════════

from uuid import uuid4


class DiscoveryCandidate(Base):
    """An unverified device found by a scanner.  Persisted to the DB so
    findings survive restarts and can be inspected / validated later.
    """

    __tablename__ = "discovery_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_scanner = Column(String(50), nullable=False, index=True)
    priority = Column(Integer, default=100)

    ip_address = Column(String(45), nullable=True, index=True)
    port = Column(Integer, nullable=True)
    mac_address = Column(String(17), nullable=True, index=True)

    raw_response = Column(String, nullable=True)          # SSDP / mDNS raw payload
    proposed_protocol = Column(String(50), nullable=True)
    proposed_name = Column(String(255), nullable=True)

    # Three-gate validation tracking
    fingerprint_hash = Column(String(64), nullable=True)
    gate_1_fingerprint = Column(Boolean, default=False)     # Gate 1 passed
    gate_2_authenticated = Column(Boolean, default=False)   # Gate 2 passed
    gate_3_capabilities = Column(Boolean, default=False)    # Gate 3 passed

    validation_status = Column(
        String(20), default="pending", index=True
    )  # pending | fingerprinting | awaiting_auth | verified | rejected
    rejection_reason = Column(String, nullable=True)
    trust_score = Column(Integer, default=0)              # 0-100

    discovered_at = Column(Float, nullable=False, default=time.time)
    last_probed_at = Column(Float, nullable=True)
    last_validated_at = Column(Float, nullable=True)

    # Link to the promoted DeviceConfig row (if promoted)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=True, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_scanner": self.source_scanner,
            "priority": self.priority,
            "ip_address": self.ip_address,
            "port": self.port,
            "mac_address": self.mac_address,
            "proposed_protocol": self.proposed_protocol,
            "proposed_name": self.proposed_name,
            "fingerprint_hash": self.fingerprint_hash,
            "gate_1_fingerprint": self.gate_1_fingerprint,
            "gate_2_authenticated": self.gate_2_authenticated,
            "gate_3_capabilities": self.gate_3_capabilities,
            "validation_status": self.validation_status,
            "rejection_reason": self.rejection_reason,
            "trust_score": self.trust_score,
            "discovered_at": self.discovered_at,
            "last_probed_at": self.last_probed_at,
            "last_validated_at": self.last_validated_at,
            "device_id": self.device_id,
        }


class Capability(Base):
    """A verified feature of a device."""

    __tablename__ = "capabilities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    protocol = Column(String(50), nullable=False)
    properties = Column(JSON, default=dict)
    read_only = Column(Boolean, default=False)
    commands = Column(JSON, default=list)
    verification_status = Column(String(20), default="unverified")  # unverified | verified | failed

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "type": self.type,
            "protocol": self.protocol,
            "properties": self.properties,
            "read_only": self.read_only,
            "commands": self.commands,
            "verification_status": self.verification_status,
        }


class AuthCredential(Base):
    """Stored authentication credentials for a device."""

    __tablename__ = "auth_credentials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    method = Column(String(30), nullable=False)  # oauth2 | api_key | cert | pin | challenge_response
    encrypted_token = Column(String, nullable=True)
    cert_hash = Column(String(64), nullable=True)
    expires_at = Column(Float, nullable=True)
    scopes = Column(JSON, default=list)
    last_used = Column(Float, nullable=True)
    rotation_due = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "method": self.method,
            "expires_at": self.expires_at,
            "scopes": self.scopes,
            "last_used": self.last_used,
            "rotation_due": self.rotation_due,
            "is_active": self.is_active,
        }


class TrustScore(Base):
    """Immutable trust score history for a device."""

    __tablename__ = "trust_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device_id"), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    computed_at = Column(Float, nullable=False, default=time.time)
    gate_1 = Column(Integer, default=0)   # 0-30
    gate_2 = Column(Integer, default=0)   # 0-40
    gate_3 = Column(Integer, default=0)   # 0-30
    deductions = Column(Integer, default=0)
    details = Column(JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "score": self.score,
            "computed_at": self.computed_at,
            "gate_1": self.gate_1,
            "gate_2": self.gate_2,
            "gate_3": self.gate_3,
            "deductions": self.deductions,
            "details": self.details,
        }
