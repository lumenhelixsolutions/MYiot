"""Device manager orchestrates plugin drivers and command dispatch."""

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from core.base_driver import BaseDriver, DeviceState
from core.plugin_loader import PluginLoader
from models.database import DeviceConfig, get_async_session_factory

logger = logging.getLogger(__name__)


class DeviceManager:
    """Owns driver instances, maps device IDs to plugins, and dispatches commands."""

    def __init__(
        self,
        registry,
        plugin_loader: PluginLoader,
        auth_manager: Optional[Any] = None,
    ):
        self.registry = registry
        self.plugin_loader = plugin_loader
        self.auth_manager = auth_manager
        self._drivers: Dict[str, BaseDriver] = {}
        self._lock = asyncio.Lock()

    async def load_devices(self) -> None:
        """Load enabled device configs from DB and instantiate drivers."""
        factory = get_async_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(DeviceConfig).where(DeviceConfig.enabled.is_(True))
            )
            configs = result.scalars().all()

        for cfg in configs:
            await self._add_driver(cfg)

    async def _add_driver(self, cfg: DeviceConfig) -> None:
        # Prefer model-specific driver lookup (allows runtime/local drivers),
        # then fall back to manufacturer-based plugin discovery.
        plugin_cls = self.plugin_loader.get_driver_class(cfg.model or "")
        if plugin_cls is None:
            plugin_cls = self.plugin_loader.get_plugin(cfg.manufacturer)
        if plugin_cls is None:
            logger.warning(
                "No plugin for manufacturer %s (model %s)",
                cfg.manufacturer,
                cfg.model,
            )
            return

        device_config = {
            "device_id": cfg.device_id,
            "manufacturer": cfg.manufacturer,
            "model": cfg.model or "unknown",
            "device_type": cfg.device_type,
            "ip": cfg.ip_address,
            "port": cfg.port,
            "protocol": cfg.protocol,
            **(cfg.custom_map or {}),
        }
        try:
            driver = plugin_cls(device_config)
        except Exception as exc:
            logger.warning(
                "Failed to instantiate driver for %s (%s): %s",
                cfg.device_id,
                cfg.manufacturer,
                exc,
            )
            return

        async with self._lock:
            self._drivers[cfg.device_id] = driver

        # Best-effort authentication. Prefer stored credentials when available,
        # otherwise attempt a no-credential handshake (simulator, Kasa, Wemo).
        credentials: Dict[str, Any] = {}
        if self.auth_manager is not None:
            if cfg.credentials_key:
                stored = self.auth_manager.get(cfg.credentials_key)
                if stored is not None:
                    credentials = stored
            else:
                stored = self.auth_manager.get(cfg.manufacturer)
                if stored is not None:
                    credentials = stored

        try:
            await driver.authenticate(credentials)
        except Exception as exc:
            logger.warning(
                "Authentication skipped for %s (%s): %s",
                cfg.device_id,
                cfg.manufacturer,
                exc,
            )

        # Publish initial driver state to the registry so stream URLs, etc.
        # are visible to API consumers immediately after add/load.
        try:
            initial_state = await driver.get_state()
            if initial_state:
                await self.registry.update(cfg.device_id, initial_state)
        except Exception as exc:
            logger.warning(
                "Failed to publish initial state for %s: %s", cfg.device_id, exc
            )

        logger.info("Instantiated driver for %s (%s)", cfg.device_id, cfg.manufacturer)

    async def authenticate(self, device_id: str, credentials: Dict[str, Any]) -> bool:
        driver = None
        async with self._lock:
            driver = self._drivers.get(device_id)
        if not driver:
            return False
        try:
            return await driver.authenticate(credentials)
        except Exception as exc:
            logger.warning("authenticate failed for %s: %s", device_id, exc)
            return False

    async def get_state(self, device_id: str) -> Optional[DeviceState]:
        driver = None
        async with self._lock:
            driver = self._drivers.get(device_id)
        if not driver:
            return None
        try:
            return await driver.get_state()
        except Exception as exc:
            logger.warning("get_state failed for %s: %s", device_id, exc)
            return None

    async def set_state(self, device_id: str, payload: Dict[str, Any]) -> bool:
        driver = None
        async with self._lock:
            driver = self._drivers.get(device_id)
        if not driver:
            logger.warning("No driver for device %s", device_id)
            return False
        try:
            success = await driver.set_state(payload)
        except Exception as exc:
            logger.warning("set_state failed for %s: %s", device_id, exc)
            return False
        if success:
            try:
                new_state = await driver.get_state()
                if new_state:
                    await self.registry.update(device_id, new_state)
            except Exception as exc:
                logger.warning(
                    "get_state refresh failed for %s after successful command: %s",
                    device_id,
                    exc,
                )
        return success

    async def add_device(self, cfg: DeviceConfig) -> None:
        await self._add_driver(cfg)

    async def remove_device(self, device_id: str) -> None:
        driver = None
        async with self._lock:
            driver = self._drivers.pop(device_id, None)
        if driver:
            try:
                await driver.disconnect()
            except Exception as exc:
                logger.warning("disconnect failed for %s: %s", device_id, exc)

    async def disconnect_all(self) -> None:
        async with self._lock:
            drivers = list(self._drivers.values())
            self._drivers.clear()
        for driver in drivers:
            try:
                await driver.disconnect()
            except Exception as exc:
                logger.warning(
                    "disconnect failed for %s: %s",
                    getattr(driver, "device_id", "unknown"),
                    exc,
                )
