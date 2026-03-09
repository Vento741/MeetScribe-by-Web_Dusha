from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from app import MeetScribeApp


class HistoryView(ctk.CTkFrame):
    """История встреч с поиском и карточками."""

    def __init__(self, parent: ctk.CTkFrame, app: MeetScribeApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Поиск
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Поиск по встречам..."
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self._search_entry.bind("<Return>", lambda e: self._refresh())

        ctk.CTkButton(search_frame, text="Найти", width=80, command=self._refresh).grid(
            row=0, column=1
        )

        # Прокручиваемый список
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._refresh()

    def _refresh(self) -> None:
        """Обновляет список встреч (с учётом поискового запроса)."""
        for widget in self._scroll.winfo_children():
            widget.destroy()

        query = self._search_entry.get().strip()
        if query:
            meetings = self._app.db.search(query)
        else:
            meetings = self._app.db.list_meetings()

        if not meetings:
            ctk.CTkLabel(self._scroll, text="Нет встреч", text_color="gray").grid(
                row=0, column=0, pady=40
            )
            return

        for i, m in enumerate(meetings):
            duration = f"{m.duration // 3600:02d}:{(m.duration % 3600) // 60:02d}:{m.duration % 60:02d}"
            card = ctk.CTkFrame(self._scroll, corner_radius=8)
            card.grid(row=i, column=0, sticky="ew", pady=3)
            card.grid_columnconfigure(1, weight=1)

            date_label = ctk.CTkLabel(card, text=m.date[:10], width=100)
            date_label.grid(row=0, column=0, padx=10, pady=8)

            title_label = ctk.CTkLabel(
                card,
                text=m.title or "Без названия",
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            )
            title_label.grid(row=0, column=1, sticky="w")

            dur_label = ctk.CTkLabel(card, text=duration, text_color="gray")
            dur_label.grid(row=0, column=2, padx=10)

            # Обработчик клика
            meeting = m
            for widget in (card, date_label, title_label, dur_label):
                widget.bind("<Button-1>", lambda e, mt=meeting: self._open_meeting(mt))
                widget.configure(cursor="hand2")

    def _open_meeting(self, meeting) -> None:
        """Открывает встречу в виде транскрипта/саммари."""
        from ui.transcript_view import TranscriptView

        view = TranscriptView(self._app._main_container, self._app, meeting)
        self._app._views["transcript"] = view
        self._app.show_view("transcript")
