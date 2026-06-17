"""
Plugin loader for Smart Home Universal Hub.

Discovers and dynamically loads manufacturer plugin modules from the
plugins package. Each plugin module should contain a class that inherits
from BaseDriver.
"""

import importlib
import importlib.util
import logging
import pkgutil
from typing import Dict, Optional, Type

from core.base_driver import BaseDriver

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Discovers and loads manufacturer plugin modules dynamically.

    Scans the plugins package for modules containing classes that inherit
    from BaseDriver, registers them by module name, and provides lookup
    by name for runtime driver instantiation.
    """

    def __init__(self, plugin_package: str = "plugins"):
        """
        Initialize the plugin loader.

        Args:
            plugin_package: Fully-qualified Python package name to scan
                for plugin modules (default: "plugins").
        """
        self.plugin_package = plugin_package
        self._plugins: Dict[str, Type[BaseDriver]] = {}
        self._model_drivers: Dict[str, Type[BaseDriver]] = {}

    def discover(self) -> Dict[str, Type[BaseDriver]]:
        """
        Discover all available plugins in the configured package.

        Scans the plugin package for non-private modules, imports each,
        and registers any classes that inherit from BaseDriver (excluding
        BaseDriver itself).

        Returns:
            Dictionary mapping plugin name (module name) to plugin class.
        """
        self._plugins.clear()

        try:
            package = importlib.import_module(self.plugin_package)
            package_path = getattr(package, "__path__", None)
            if package_path is None:
                logger.warning(
                    "Plugin package '%s' has no __path__", self.plugin_package
                )
                return self._plugins

            for _, name, ispkg in pkgutil.iter_modules(package_path):
                if ispkg or name.startswith("_"):
                    continue

                full_name = f"{self.plugin_package}.{name}"
                try:
                    module = importlib.import_module(full_name)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseDriver)
                            and attr is not BaseDriver
                        ):
                            self._plugins[name] = attr
                            logger.debug(
                                "Registered plugin '%s' -> %s.%s",
                                name,
                                full_name,
                                attr_name,
                            )
                    if hasattr(module, "register"):
                        try:
                            module.register(self)
                        except Exception as exc:
                            logger.warning(
                                "Failed to register model drivers for plugin '%s': %s",
                                name,
                                exc,
                            )
                except Exception as exc:
                    logger.warning("Failed to load plugin '%s': %s", full_name, exc)
                    continue

        except ImportError as exc:
            logger.warning(
                "Plugin package '%s' not found: %s", self.plugin_package, exc
            )

        logger.info(
            "Plugin discovery complete — %d plugin(s) registered", len(self._plugins)
        )
        return self._plugins

    def register_model_driver(
        self, model: str, driver_cls: Type[BaseDriver]
    ) -> None:
        """Register a driver class for a specific device model string."""
        self._model_drivers[model] = driver_cls
        logger.info("Registered model driver '%s' -> %s", model, driver_cls.__name__)

    def get_driver_class(self, model: str) -> Optional[Type[BaseDriver]]:
        """Return the model-specific driver class, if any."""
        return self._model_drivers.get(model)

    def get_plugin(self, name: str) -> Optional[Type[BaseDriver]]:
        """
        Get a plugin class by name.

        Args:
            name: Plugin module name (e.g., "philips_hue", "tp_link_kasa").

        Returns:
            The plugin driver class, or None if not found.
        """
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        """
        List names of all discovered plugins.

        Returns:
            List of registered plugin names.
        """
        return list(self._plugins.keys())

    def has_plugin(self, name: str) -> bool:
        """
        Check if a plugin is available.

        Args:
            name: Plugin module name.

        Returns:
            True if the plugin is registered, False otherwise.
        """
        return name in self._plugins
