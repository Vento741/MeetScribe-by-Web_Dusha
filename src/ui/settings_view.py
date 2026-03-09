from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from audio.recorder import list_audio_devices
from config import save_config

if TYPE_CHECKING:
    from app import MeetScribeApp


class SettingsView(ctk.CTkFrame):
    """Панель настроек приложения."""

    def __init__(self, parent: ctk.CTkFrame, app: MeetScribeApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app
        cfg = app.config

        self.grid_columnconfigure(1, weight=1)

        row = 0

        # Заголовок
        ctk.CTkLabel(
            self, text="Настройки", font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 20))
        row += 1

        # API ключ
        ctk.CTkLabel(self, text="API ключ OpenRouter:").grid(
            row=row, column=0, sticky="w", pady=5
        )
        self._api_entry = ctk.CTkEntry(self, show="*", width=400)
        self._api_entry.insert(0, cfg.api_key)
        self._api_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))
        row += 1

        # Модель
        ctk.CTkLabel(self, text="Модель:").grid(row=row, column=0, sticky="w", pady=5)
        self._model_entry = ctk.CTkEntry(self, width=400)
        self._model_entry.insert(0, cfg.model)
        self._model_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))
        row += 1

        # Тема
        ctk.CTkLabel(self, text="Тема:").grid(row=row, column=0, sticky="w", pady=5)
        self._theme_var = ctk.StringVar(value=cfg.theme)
        theme_frame = ctk.CTkFrame(self, fg_color="transparent")
        theme_frame.grid(row=row, column=1, sticky="w", pady=5, padx=(10, 0))
        for val, label in [
            ("dark", "Тёмная"),
            ("light", "Светлая"),
            ("system", "Системная"),
        ]:
            ctk.CTkRadioButton(
                theme_frame, text=label, variable=self._theme_var, value=val
            ).pack(side="left", padx=10)
        row += 1

        # Аудиоустройства
        devices = list_audio_devices()
        device_names = [f"{d.index}: {d.name}" for d in devices]

        ctk.CTkLabel(self, text="Микрофон:").grid(row=row, column=0, sticky="w", pady=5)
        mic_names = [n for n, d in zip(device_names, devices) if not d.is_loopback] or [
            "(не найдено)"
        ]
        self._mic_combo = ctk.CTkComboBox(self, values=mic_names, width=400)
        self._mic_combo.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))
        row += 1

        ctk.CTkLabel(self, text="Системный звук:").grid(
            row=row, column=0, sticky="w", pady=5
        )
        loop_names = [n for n, d in zip(device_names, devices) if d.is_loopback] or [
            "(не найдено)"
        ]
        self._loop_combo = ctk.CTkComboBox(self, values=loop_names, width=400)
        self._loop_combo.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))
        row += 1

        # Горячие клавиши
        ctk.CTkLabel(self, text="Старт/стоп записи:").grid(
            row=row, column=0, sticky="w", pady=5
        )
        self._hotkey_entry = ctk.CTkEntry(self, width=200)
        self._hotkey_entry.insert(0, cfg.hotkey_toggle)
        self._hotkey_entry.grid(row=row, column=1, sticky="w", pady=5, padx=(10, 0))
        row += 1

        # Папка сохранения
        ctk.CTkLabel(self, text="Папка сохранения:").grid(
            row=row, column=0, sticky="w", pady=5
        )
        self._dir_entry = ctk.CTkEntry(self, width=400)
        self._dir_entry.insert(0, cfg.save_dir)
        self._dir_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))
        row += 1

        # Шаблон промпта
        ctk.CTkLabel(self, text="Шаблон промпта:").grid(
            row=row, column=0, sticky="nw", pady=5
        )
        self._prompt_text = ctk.CTkTextbox(self, height=150, width=400)
        self._prompt_text.insert("1.0", cfg.prompt_template)
        self._prompt_text.grid(row=row, column=1, sticky="ew", pady=5, padx=(10, 0))
        row += 1

        # Кнопка сохранения
        ctk.CTkButton(self, text="Сохранить", width=200, command=self._save).grid(
            row=row, column=1, sticky="w", pady=20, padx=(10, 0)
        )

    def _save(self) -> None:
        """Сохраняет настройки в конфиг-файл."""
        cfg = self._app.config
        cfg.api_key = self._api_entry.get().strip()
        cfg.model = self._model_entry.get().strip()
        cfg.theme = self._theme_var.get()
        cfg.hotkey_toggle = self._hotkey_entry.get().strip()
        cfg.save_dir = self._dir_entry.get().strip()
        cfg.prompt_template = self._prompt_text.get("1.0", "end").strip()

        # Парсинг индексов устройств
        mic_sel = self._mic_combo.get()
        loop_sel = self._loop_combo.get()
        cfg.mic_device = (
            int(mic_sel.split(":")[0]) if mic_sel and mic_sel[0].isdigit() else None
        )
        cfg.loopback_device = (
            int(loop_sel.split(":")[0]) if loop_sel and loop_sel[0].isdigit() else None
        )

        ctk.set_appearance_mode(cfg.theme)
        save_config(cfg)
        self._app.set_status("Настройки сохранены")
