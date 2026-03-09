from __future__ import annotations

from typing import Callable

import customtkinter as ctk

_ACCENT = "#2BA5B5"
_ACTIVE_BG = ("#D4F5F5", "#1A3A3F")


class Sidebar(ctk.CTkFrame):
    """Боковая панель навигации."""

    def __init__(self, parent: ctk.CTk, on_navigate: Callable[[str], None]) -> None:
        super().__init__(
            parent, width=200, corner_radius=0,
            border_width=1, border_color=("gray80", "gray25"),
        )
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}

        # Логотип
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(padx=16, pady=(24, 8))

        ctk.CTkLabel(
            logo_frame, text="MeetScribe",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=_ACCENT,
        ).pack()

        ctk.CTkLabel(
            logo_frame, text="протокол встреч",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray55"),
        ).pack()

        # Разделитель
        ctk.CTkFrame(
            self, height=1, fg_color=("gray80", "gray25"),
        ).pack(fill="x", padx=16, pady=(12, 16))

        # Кнопки навигации
        self._add_button("recording", "🎙  Запись")
        self._add_button("history", "📋  История")
        self._add_button("settings", "⚙  Настройки")

        # Распорка
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Версия
        ctk.CTkLabel(
            self, text="v1.0.0",
            text_color=("gray60", "gray45"),
            font=ctk.CTkFont(size=10),
        ).pack(pady=(0, 12))

    def _add_button(self, name: str, label: str) -> None:
        """Добавляет кнопку навигации в боковую панель."""
        btn = ctk.CTkButton(
            self,
            text=label,
            anchor="w",
            height=42,
            corner_radius=8,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray28"),
            font=ctk.CTkFont(size=13),
            command=lambda: self._on_navigate(name),
        )
        btn.pack(fill="x", padx=10, pady=2)
        self._buttons[name] = btn

    def set_active(self, name: str) -> None:
        """Подсвечивает активную кнопку навигации."""
        for key, btn in self._buttons.items():
            if key == name:
                btn.configure(
                    fg_color=_ACTIVE_BG,
                    text_color=_ACCENT,
                    font=ctk.CTkFont(size=13, weight="bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("gray10", "gray90"),
                    font=ctk.CTkFont(size=13),
                )
