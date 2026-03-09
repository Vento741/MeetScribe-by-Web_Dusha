from __future__ import annotations

import logging
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)


class GlobalHotkeys:
    """Глобальные горячие клавиши для управления записью."""

    def __init__(self) -> None:
        self._listener: keyboard.GlobalHotKeys | None = None
        self._bindings: dict[str, Callable] = {}

    def register(self, hotkey: str, callback: Callable) -> None:
        """Регистрирует горячую клавишу с указанным колбэком."""
        self._bindings[self._normalize(hotkey)] = callback

    def start(self) -> None:
        """Запускает прослушивание горячих клавиш."""
        if self._listener:
            self.stop()
        try:
            self._listener = keyboard.GlobalHotKeys(self._bindings)
            self._listener.daemon = True
            self._listener.start()
            logger.info(
                "Горячие клавиши зарегистрированы: %s", list(self._bindings.keys())
            )
        except Exception as e:
            logger.error("Не удалось зарегистрировать горячие клавиши: %s", e)

    def stop(self) -> None:
        """Останавливает прослушивание горячих клавиш."""
        if self._listener:
            self._listener.stop()
            self._listener = None

    @staticmethod
    def _normalize(hotkey: str) -> str:
        """Нормализует строку горячей клавиши в формат pynput."""
        parts = hotkey.lower().replace(" ", "").split("+")
        mapped = []
        for p in parts:
            if p in ("ctrl", "control"):
                mapped.append("<ctrl>")
            elif p in ("shift",):
                mapped.append("<shift>")
            elif p in ("alt",):
                mapped.append("<alt>")
            else:
                mapped.append(p)
        return "+".join(mapped)
