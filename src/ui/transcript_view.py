from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from storage.database import Meeting
from storage.exporter import export_to_markdown

if TYPE_CHECKING:
    from app import MeetScribeApp


class TranscriptView(ctk.CTkFrame):
    """Просмотр транскрипта и саммари встречи с вкладками."""

    def __init__(self, parent: ctk.CTkFrame, app: MeetScribeApp, meeting: Meeting) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app
        self._meeting = meeting

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Название (редактируемое)
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        title_frame.grid_columnconfigure(0, weight=1)

        self._title_entry = ctk.CTkEntry(title_frame, font=ctk.CTkFont(size=20, weight="bold"))
        self._title_entry.insert(0, meeting.title or "")
        self._title_entry.grid(row=0, column=0, sticky="ew")
        self._title_entry.bind("<Return>", self._save_title)

        # Информационная строка
        duration = f"{meeting.duration // 3600:02d}:{(meeting.duration % 3600) // 60:02d}:{meeting.duration % 60:02d}"
        info = ctk.CTkLabel(self, text=f"{meeting.date[:10]}  |  {duration}", text_color="gray")
        info.grid(row=1, column=0, sticky="w", pady=(0, 10))

        # Вкладки
        self._tabview = ctk.CTkTabview(self)
        self._tabview.grid(row=2, column=0, sticky="nsew")

        tab_summary = self._tabview.add("Саммари")
        tab_transcript = self._tabview.add("Транскрипт")

        # Текст саммари
        self._summary_text = ctk.CTkTextbox(tab_summary, wrap="word")
        self._summary_text.pack(fill="both", expand=True)
        self._summary_text.insert("1.0", meeting.summary or "(нет саммари)")

        # Текст транскрипта
        self._transcript_text = ctk.CTkTextbox(tab_transcript, wrap="word")
        self._transcript_text.pack(fill="both", expand=True)
        self._transcript_text.insert("1.0", meeting.transcript or "(нет транскрипта)")

        # Кнопки
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", pady=10)

        ctk.CTkButton(btn_frame, text="Копировать саммари", command=self._copy_summary).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Экспорт .md", command=self._export_md).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Назад", fg_color="gray", command=lambda: self._app.show_view("history")).pack(side="right", padx=5)

    def _save_title(self, event=None) -> None:
        """Сохраняет новое название встречи."""
        new_title = self._title_entry.get().strip()
        if new_title:
            self._app.db.update_title(self._meeting.id, new_title)
            self._app.set_status(f"Название обновлено: {new_title}")

    def _copy_summary(self) -> None:
        """Копирует саммари в буфер обмена."""
        text = self._summary_text.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self._app.set_status("Саммари скопировано в буфер обмена")

    def _export_md(self) -> None:
        """Экспортирует встречу в Markdown-файл."""
        from pathlib import Path
        save_dir = Path(self._app.config.save_dir)
        path = export_to_markdown(self._meeting, save_dir)
        self._app.set_status(f"Экспортировано: {path}")
