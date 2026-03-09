from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class Sidebar(ctk.CTkFrame):
    """Боковая панель навигации."""

    def __init__(self, parent: ctk.CTk, on_navigate: Callable[[str], None]) -> None:
        super().__init__(parent, width=200, corner_radius=0)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}

        # Логотип
        logo = ctk.CTkLabel(
            self, text="MeetScribe", font=ctk.CTkFont(size=20, weight="bold")
        )
        logo.pack(padx=20, pady=(20, 30))

        # Кнопки навигации
        self._add_button("recording", "Запись")
        self._add_button("history", "История")
        self._add_button("settings", "Настройки")

        # Распорка
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Версия
        ver = ctk.CTkLabel(self, text="v1.0.0", text_color="gray")
        ver.pack(pady=10)

    def _add_button(self, name: str, label: str) -> None:
        """Добавляет кнопку навигации в боковую панель."""
        btn = ctk.CTkButton(
            self,
            text=label,
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            command=lambda: self._on_navigate(name),
        )
        btn.pack(fill="x", padx=10, pady=2)
        self._buttons[name] = btn

    def set_active(self, name: str) -> None:
        """Подсвечивает активную кнопку навигации."""
        for key, btn in self._buttons.items():
            if key == name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")
