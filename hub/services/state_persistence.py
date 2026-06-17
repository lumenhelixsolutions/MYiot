"""State persistence adapter.

Subscribes to StateRegistry updates and writes throttled snapshots to SQLite.
"""

import asyncio
import logging
from typing import Dict

from sqlalchemy import select

from core.base_driver import DeviceState
from models.database import get_async_session_factory, update_device_state

logger = logging.getLogger(__name__)


class StatePersistenceAdapter:
    """Writes device state snapshots to the database on a debounced schedule."""

    def __init__(self, debounce_seconds: float = 2.0):
        self.debounce_seconds = debounce_seconds
        self._pending: Dict[str, DeviceState] = {}
        self._task: asyncio.Task | None = None
        self._registry = None

    def attach(self, registry) -> None:
        """Subscribe to registry updates."""
        self._registry = registry
        registry.subscribe(self._on_state_change)
        logger.info("StatePersistenceAdapter attached")

    async def detach(self) -> None:
        """Cancel pending writes and unsubscribe."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._registry:
            # Note: StateRegistry.unsubscribe expects the same callback object.
            self._registry.unsubscribe(self._on_state_change)

    async def _on_state_change(self, device_id: str, state: DeviceState) -> None:
        self._pending[device_id] = state
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._flush_after_debounce())

    async def _flush_after_debounce(self) -> None:
        await asyncio.sleep(self.debounce_seconds)
        await self.flush()

    async def flush(self) -> None:
        """Flush any pending state snapshots to the database immediately."""
        await self._flush()

    async def _flush(self) -> None:
        if not self._pending:
            return

        batch = dict(self._pending)
        self._pending.clear()

        factory = get_async_session_factory()
        async with factory() as session:
            try:
                for device_id, state in batch.items():
                    await update_device_state(
                        session,
                        device_id,
                        {
                            "online": state.online,
                            "state": state.state,
                            "last_updated": state.last_updated,
                            "manufacturer": state.manufacturer,
                            "model": state.model,
                            "device_type": state.device_type,
                        },
                    )
                await session.commit()
            except Exception as exc:
                logger.warning("Failed to persist state batch: %s", exc)
                await session.rollback()
            finally:
                if self._pending:
                    self._task = asyncio.create_task(self._flush_after_debounce())


async def load_devices_into_registry(registry) -> None:
    """Hydrate the registry from persisted device configs."""
    from core.base_driver import DeviceState as DS
    from models.database import DeviceConfig, get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(select(DeviceConfig).where(DeviceConfig.enabled.is_(True)))
        configs = result.scalars().all()
        # Read lazy / detached attributes while still inside the session context.
        device_snapshots = [
            {
                "device_id": cfg.device_id,
                "manufacturer": cfg.manufacturer,
                "model": cfg.model or "unknown",
                "device_type": cfg.device_type,
                "last_state": cfg.last_state or {},
            }
            for cfg in configs
        ]

    for snapshot in device_snapshots:
        last_state = snapshot["last_state"]
        state = DS(
            device_id=snapshot["device_id"],
            manufacturer=snapshot["manufacturer"],
            model=snapshot["model"],
            device_type=snapshot["device_type"],
            online=last_state.get("online", False),
            state=last_state.get("state", {}),
            last_updated=last_state.get("last_updated", 0.0),
        )
        await registry.update(snapshot["device_id"], state)
        logger.info("Restored device %s from database", snapshot["device_id"])
