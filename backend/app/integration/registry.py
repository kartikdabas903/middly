"""Connector plugin discovery.

Scans `CONNECTORS_PATH/*/connector.py`, imports each module and registers every
concrete `BaseConnector` subclass by its `key`. Adding a department means adding
a folder — the workflow engine and services resolve connectors by key only.
"""
from __future__ import annotations

import importlib.util
import inspect
import logging
import re
import sys
import threading
from pathlib import Path

from app.core.config import get_settings
from app.integration.sdk import BaseConnector

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    def __init__(self) -> None:
        self._classes: dict[str, type[BaseConnector]] = {}
        self._modules: dict[str, str] = {}
        self._lock = threading.Lock()
        self._loaded = False

    def discover(self, path: str | None = None, force: bool = False) -> dict[str, type[BaseConnector]]:
        with self._lock:
            if self._loaded and not force:
                return self._classes
            root = Path(path or get_settings().connectors_path)
            if not root.exists():
                logger.error("Connector plugin directory not found: %s", root)
                self._loaded = True
                return self._classes
            for plugin_file in sorted(root.glob("*/connector.py")):
                self._load_file(plugin_file)
            self._loaded = True
            logger.info("Registered connectors: %s", ", ".join(sorted(self._classes)))
            return self._classes

    def _load_file(self, plugin_file: Path) -> None:
        module_name = "middly_connector_" + re.sub(r"\W", "_", plugin_file.parent.name)
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec is None or spec.loader is None:
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception:  # a broken plugin must never take the platform down
            logger.exception("Failed to load connector plugin %s", plugin_file)
            return
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseConnector) and obj is not BaseConnector and not inspect.isabstract(obj) and obj.key:
                if obj.key in self._classes and self._classes[obj.key] is not obj:
                    logger.error("Duplicate connector key %s in %s — ignored", obj.key, plugin_file)
                    continue
                self._classes[obj.key] = obj
                self._modules[obj.key] = str(plugin_file.relative_to(plugin_file.parents[1]))

    def register(self, cls: type[BaseConnector], module: str = "in-process") -> None:
        """Programmatic registration (used by tests)."""
        self._classes[cls.key] = cls
        self._modules[cls.key] = module

    def get_class(self, key: str) -> type[BaseConnector] | None:
        self.discover()
        return self._classes.get(key)

    def all(self) -> dict[str, type[BaseConnector]]:
        return dict(self.discover())

    def module_of(self, key: str) -> str:
        return self._modules.get(key, "unknown")


registry = ConnectorRegistry()
