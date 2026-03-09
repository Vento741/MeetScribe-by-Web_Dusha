from __future__ import annotations

import asyncio
import logging
import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from storage.database import Meeting
from storage.exporter import (
    export_to_html,
    export_to_markdown,
    export_to_pdf,
    export_to_txt,
    format_duration,
)

if TYPE_CHECKING:
    from app import MeetScribeApp

logger = logging.getLogger(__name__)


class TranscriptView(ctk.CTkFrame):
    """Просмотр транскрипта и саммари встречи с вкладками."""

    def __init__(
        self, parent: ctk.CTkFrame, app: MeetScribeApp, meeting: Meeting
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app
        self._meeting = meeting

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Название (редактируемое)
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        title_frame.grid_columnconfigure(0, weight=1)

        self._title_entry = ctk.CTkEntry(
            title_frame, font=ctk.CTkFont(size=20, weight="bold")
        )
        self._title_entry.insert(0, meeting.title or "")
        self._title_entry.grid(row=0, column=0, sticky="ew")
        self._title_entry.bind("<Return>", self._save_title)

        # Информационная строка
        duration = format_duration(meeting.duration)
        info = ctk.CTkLabel(
            self, text=f"{meeting.date[:10]}  |  {duration}", text_color="gray"
        )
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

        ctk.CTkButton(
            btn_frame, text="Копировать саммари", command=self._copy_summary
        ).pack(side="left", padx=5)

        self._regen_btn = ctk.CTkButton(
            btn_frame, text="Перегенерировать", command=self._regenerate_summary
        )
        self._regen_btn.pack(side="left", padx=5)

        self._regen_prompt_btn = ctk.CTkButton(
            btn_frame, text="С другим промптом...", command=self._regenerate_with_prompt
        )
        self._regen_prompt_btn.pack(side="left", padx=5)

        self._export_btn = ctk.CTkButton(
            btn_frame, text="Экспорт...", command=self._show_export_menu
        )
        self._export_btn.pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Назад",
            fg_color="gray",
            command=lambda: self._app.show_view("history"),
        ).pack(side="right", padx=5)

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

    # ═══════════════════════ Перегенерация ═══════════════════════

    def _regenerate_summary(self) -> None:
        """Перегенерирует саммари с текущим промптом из настроек."""
        if not self._meeting.transcript:
            self._app.set_status("Нет транскрипта для генерации саммари")
            return
        self._run_regeneration(self._app.config.prompt_template)

    def _regenerate_with_prompt(self) -> None:
        """Открывает модальное окно для редактирования промпта перед перегенерацией."""
        if not self._meeting.transcript:
            self._app.set_status("Нет транскрипта для генерации саммари")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Промпт для саммари")
        dialog.geometry("600x400")
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Отредактируйте промпт:",
        ).pack(pady=(10, 5), padx=10, anchor="w")

        prompt_box = ctk.CTkTextbox(dialog, height=250)
        prompt_box.pack(fill="both", expand=True, padx=10, pady=5)
        prompt_box.insert(
            "1.0",
            self._meeting.prompt_used or self._app.config.prompt_template,
        )

        def on_generate():
            prompt = prompt_box.get("1.0", "end").strip()
            dialog.destroy()
            self._run_regeneration(prompt)

        ctk.CTkButton(dialog, text="Генерировать", command=on_generate).pack(pady=10)

    def _run_regeneration(self, prompt: str) -> None:
        """Запускает перегенерацию саммари в фоновом потоке."""
        from ai.summarizer import generate_summary

        self._app.set_status("Генерация саммари...")
        self._regen_btn.configure(state="disabled", text="Генерация...")
        self._regen_prompt_btn.configure(state="disabled")

        cfg = self._app.config

        def run():
            loop = asyncio.new_event_loop()
            try:
                summary = loop.run_until_complete(
                    generate_summary(
                        self._meeting.transcript,
                        prompt,
                        cfg.api_key,
                        cfg.model,
                    )
                )
                self.after(0, lambda: self._on_regen_done(summary, prompt))
            except Exception:
                import traceback

                err = traceback.format_exc()
                logger.error("Ошибка перегенерации: %s", err)
                self.after(0, lambda: self._on_regen_error(err))
            finally:
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def _on_regen_done(self, summary: str, prompt: str) -> None:
        """Обработка результата перегенерации."""
        self._app.db.update_summary(self._meeting.id, summary, prompt)
        self._meeting.summary = summary
        self._meeting.prompt_used = prompt
        self._summary_text.delete("1.0", "end")
        self._summary_text.insert("1.0", summary or "(нет саммари)")
        self._regen_btn.configure(state="normal", text="Перегенерировать")
        self._regen_prompt_btn.configure(state="normal")
        self._app.set_status("Саммари обновлено")

    def _on_regen_error(self, err: str) -> None:
        """Обработка ошибки перегенерации."""
        self._regen_btn.configure(state="normal", text="Перегенерировать")
        self._regen_prompt_btn.configure(state="normal")
        self._app.set_status(f"Ошибка: {err[:200]}")

    # ═══════════════════════ Экспорт ═══════════════════════

    def _show_export_menu(self) -> None:
        """Показывает выпадающее меню выбора формата экспорта."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="PDF (.pdf)", command=lambda: self._export("pdf"))
        menu.add_command(label="Markdown (.md)", command=lambda: self._export("md"))
        menu.add_command(label="HTML (.html)", command=lambda: self._export("html"))
        menu.add_command(label="Текст (.txt)", command=lambda: self._export("txt"))
        btn = self._export_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        menu.tk_popup(x, y)

    def _export(self, fmt: str) -> None:
        """Экспортирует встречу в выбранном формате."""
        from pathlib import Path

        save_dir = Path(self._app.config.save_dir)
        exporters = {
            "md": export_to_markdown,
            "txt": export_to_txt,
            "html": export_to_html,
            "pdf": export_to_pdf,
        }
        try:
            path = exporters[fmt](self._meeting, save_dir)
            self._app.set_status(f"Экспортировано: {path}")
        except Exception as e:
            logger.error("Ошибка экспорта %s: %s", fmt, e)
            self._app.set_status(f"Ошибка экспорта: {e}")
