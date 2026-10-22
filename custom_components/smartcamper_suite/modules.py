from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import ModuleName


@dataclass(slots=True)
class ModuleRuntime:
    name: ModuleName
    enabled: bool = False
    started: bool = False
    error: str | None = None

    async def async_setup(self, _context: Any) -> None:
        if self.enabled:
            self.started = True

    async def async_unload(self) -> None:
        self.started = False


class ModuleManager:
    def __init__(self, enabled: dict[str, bool] | None = None) -> None:
        enabled = enabled or {}
        self.modules = {name: ModuleRuntime(name, bool(enabled.get(name.value, False))) for name in ModuleName}

    async def async_setup(self, context: Any) -> None:
        for runtime in self.modules.values():
            try:
                await runtime.async_setup(context)
            except Exception as err:  # noqa: BLE001  # isolate module failures
                runtime.error = type(err).__name__

    async def async_unload(self) -> None:
        for runtime in self.modules.values():
            await runtime.async_unload()

    def set_enabled(self, module: ModuleName, enabled: bool) -> None:
        self.modules[module].enabled = enabled

    def status(self) -> dict[str, dict[str, Any]]:
        return {name.value: {"enabled": item.enabled, "started": item.started, "error": item.error} for name, item in self.modules.items()}
