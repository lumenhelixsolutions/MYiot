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
