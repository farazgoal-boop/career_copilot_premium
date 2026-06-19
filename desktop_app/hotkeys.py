"""Hotkey registration for desktop interview mode."""

from __future__ import annotations

from typing import Callable

try:
    import keyboard  # type: ignore[import-not-found]

    GLOBAL_HOTKEY_RUNTIME_AVAILABLE = True
except ImportError:
    keyboard = None
    GLOBAL_HOTKEY_RUNTIME_AVAILABLE = False


class GlobalHotkeyBackend:
    def __init__(self) -> None:
        if not GLOBAL_HOTKEY_RUNTIME_AVAILABLE:
            raise RuntimeError("keyboard runtime is required for global hotkeys.")

        self._handles: dict[str, object] = {}

    def register(self, key: str, callback: Callable[[], object]) -> None:
        normalized = key.lower()
        self.unregister(normalized)
        self._handles[normalized] = keyboard.add_hotkey(normalized, callback)

    def unregister(self, key: str) -> None:
        normalized = key.lower()
        handle = self._handles.pop(normalized, None)
        if handle is not None:
            keyboard.remove_hotkey(handle)

    def clear(self) -> None:
        for key in list(self._handles):
            self.unregister(key)


def global_hotkey_runtime_available() -> bool:
    return GLOBAL_HOTKEY_RUNTIME_AVAILABLE


class HotkeyManager:
    def __init__(self, use_global_backend: bool = False) -> None:
        self._callbacks: dict[str, Callable[[], object]] = {}
        self._use_global_backend = use_global_backend and GLOBAL_HOTKEY_RUNTIME_AVAILABLE
        self._global_backend = GlobalHotkeyBackend() if self._use_global_backend else None

    @property
    def using_global_backend(self) -> bool:
        return self._global_backend is not None

    def register(self, key: str, callback: Callable[[], object]) -> None:
        normalized = key.upper()
        self._callbacks[normalized] = callback
        if self._global_backend is not None:
            self._global_backend.register(normalized, callback)

    def unregister(self, key: str) -> None:
        normalized = key.upper()
        self._callbacks.pop(normalized, None)
        if self._global_backend is not None:
            self._global_backend.unregister(normalized)

    def shutdown(self) -> None:
        if self._global_backend is not None:
            self._global_backend.clear()

    def trigger(self, key: str) -> object:
        normalized = key.upper()
        if normalized not in self._callbacks:
            raise KeyError(f"No hotkey registered for {normalized}.")
        return self._callbacks[normalized]()