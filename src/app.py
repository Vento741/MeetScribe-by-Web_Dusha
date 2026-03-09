from __future__ import annotations

import customtkinter as ctk

from config import AppConfig, load_config, save_config
from storage.database import MeetingDB
from ui.sidebar import Sidebar


class MeetScribeApp(ctk.CTk):
    """Главное окно приложения MeetScribe."""

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.config.appdata_dir.mkdir(parents=True, exist_ok=True)
        self.db = MeetingDB(self.config.db_path)

        ctk.set_appearance_mode(self.config.theme)
        ctk.set_default_color_theme("blue")

        self.title("MeetScribe")
        self.geometry("1100x700")
        self.minsize(900, 600)

        # Разметка
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._views: dict[str, ctk.CTkFrame] = {}
        self._current_view: str = ""

        self.sidebar = Sidebar(self, on_navigate=self.show_view)
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        self._main_container = ctk.CTkFrame(self, fg_color="transparent")
        self._main_container.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self._main_container.grid_columnconfigure(0, weight=1)
        self._main_container.grid_rowconfigure(0, weight=1)

        # Строка статуса
        self._statusbar = ctk.CTkLabel(self, text="Готово", anchor="w", height=25)
        self._statusbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)

        # Горячие клавиши
        from ui.hotkeys import GlobalHotkeys
        self._hotkeys = GlobalHotkeys()
        self._hotkeys.register(self.config.hotkey_toggle, self._hotkey_toggle_recording)
        self._hotkeys.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Начальный вид
        self.show_view("recording")

    def show_view(self, name: str) -> None:
        """Переключает активный вид."""
        if self._current_view == name:
            return

        # Скрываем текущий вид
        for view in self._views.values():
            view.grid_forget()

        # Создаём или показываем целевой вид
        if name not in self._views:
            self._views[name] = self._create_view(name)

        self._views[name].grid(row=0, column=0, sticky="nsew")
        self._current_view = name
        self.sidebar.set_active(name)

    def _create_view(self, name: str) -> ctk.CTkFrame:
        """Создаёт вид по имени (ленивая инициализация)."""
        if name == "recording":
            from ui.recording_view import RecordingView
            return RecordingView(self._main_container, app=self)
        elif name == "history":
            from ui.history_view import HistoryView
            return HistoryView(self._main_container, app=self)
        elif name == "settings":
            from ui.settings_view import SettingsView
            return SettingsView(self._main_container, app=self)
        else:
            placeholder = ctk.CTkFrame(self._main_container)
            ctk.CTkLabel(placeholder, text=f"Вид: {name}").pack()
            return placeholder

    def set_status(self, text: str) -> None:
        """Обновляет текст строки статуса."""
        self._statusbar.configure(text=text)

    def _hotkey_toggle_recording(self) -> None:
        """Обработчик горячей клавиши старт/стоп записи."""
        if "recording" in self._views:
            self.after(0, self._views["recording"]._toggle_recording)

    def _on_close(self) -> None:
        """Корректное завершение приложения."""
        self._hotkeys.stop()
        self.db.close()
        self.destroy()
