from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

import customtkinter as ctk

from audio.recorder import AudioRecorder

if TYPE_CHECKING:
    from app import MeetScribeApp


class RecordingView(ctk.CTkFrame):
    """Экран записи встречи с таймером и индикаторами уровня звука."""

    def __init__(self, parent: ctk.CTkFrame, app: MeetScribeApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app
        self._recorder = AudioRecorder()

        self.grid_columnconfigure(0, weight=1)

        # Заголовок
        title = ctk.CTkLabel(
            self, text="Запись встречи", font=ctk.CTkFont(size=24, weight="bold")
        )
        title.grid(row=0, column=0, pady=(0, 20))

        # Таймер
        self._timer_label = ctk.CTkLabel(
            self, text="00:00:00", font=ctk.CTkFont(size=48, family="Consolas")
        )
        self._timer_label.grid(row=1, column=0, pady=10)

        # Индикаторы уровня звука
        meters_frame = ctk.CTkFrame(self, fg_color="transparent")
        meters_frame.grid(row=2, column=0, pady=20)

        ctk.CTkLabel(meters_frame, text="Микрофон:").grid(
            row=0, column=0, padx=(0, 10), sticky="w"
        )
        self._mic_bar = ctk.CTkProgressBar(meters_frame, width=300)
        self._mic_bar.grid(row=0, column=1)
        self._mic_bar.set(0)

        ctk.CTkLabel(meters_frame, text="Система:").grid(
            row=1, column=0, padx=(0, 10), sticky="w", pady=5
        )
        self._sys_bar = ctk.CTkProgressBar(meters_frame, width=300)
        self._sys_bar.grid(row=1, column=1, pady=5)
        self._sys_bar.set(0)

        # Кнопка записи
        self._rec_button = ctk.CTkButton(
            self,
            text="Начать запись",
            width=250,
            height=50,
            font=ctk.CTkFont(size=18),
            fg_color="#c0392b",
            hover_color="#e74c3c",
            command=self._toggle_recording,
        )
        self._rec_button.grid(row=3, column=0, pady=30)

        # Статус
        self._status_label = ctk.CTkLabel(
            self, text='Выберите устройства в настройках и нажмите "Начать запись"'
        )
        self._status_label.grid(row=4, column=0)

    def _toggle_recording(self) -> None:
        """Переключает состояние записи."""
        if not self._recorder.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        """Начинает запись аудио."""
        cfg = self._app.config
        if not cfg.api_key:
            self._status_label.configure(text="Укажите API ключ в настройках!")
            return

        self._recorder.set_level_callback(self._on_audio_level)

        import tempfile
        from pathlib import Path

        temp_dir = Path(tempfile.gettempdir()) / "MeetScribe"
        self._recorder.start(
            output_dir=temp_dir,
            mic_device=cfg.mic_device,
            loopback_device=cfg.loopback_device,
        )

        self._rec_button.configure(
            text="Остановить и обработать", fg_color="#27ae60", hover_color="#2ecc71"
        )
        self._status_label.configure(text="Запись идёт...")
        self._app.set_status("Запись идёт...")
        self._update_timer()

    def _stop_recording(self) -> None:
        """Останавливает запись и запускает обработку."""
        self._rec_button.configure(state="disabled", text="Обработка...")
        self._status_label.configure(text="Остановка записи...")

        def process():
            mic_path, sys_path = self._recorder.stop()
            self.after(0, lambda: self._on_recording_stopped(mic_path, sys_path))

        threading.Thread(target=process, daemon=True).start()

    def _on_recording_stopped(self, mic_path, sys_path) -> None:
        """Обрабатывает остановку записи: микширование и запуск пайплайна."""
        from audio.mixer import mix_audio
        from pathlib import Path
        import tempfile

        temp_dir = Path(tempfile.gettempdir()) / "MeetScribe"
        mixed_path = temp_dir / f"mixed_{time.strftime('%Y%m%d_%H%M%S')}.wav"

        try:
            mix_audio(mic_path, sys_path, mixed_path)
        except Exception:
            mixed_path = mic_path or sys_path

        self._process_audio(mixed_path)

    def _process_audio(self, audio_path) -> None:
        """Запускает пайплайн транскрибации и генерации саммари."""
        import asyncio
        from ai.transcriber import transcribe_audio
        from ai.summarizer import generate_summary

        cfg = self._app.config

        self._status_label.configure(text="Транскрибация...")
        self._app.set_status("Транскрибация...")

        def run_pipeline():
            loop = asyncio.new_event_loop()

            try:
                transcript = loop.run_until_complete(
                    transcribe_audio(audio_path, cfg.api_key, cfg.model)
                )
                self.after(
                    0, lambda: self._status_label.configure(text="Генерация саммари...")
                )
                self.after(0, lambda: self._app.set_status("Генерация саммари..."))

                summary = loop.run_until_complete(
                    generate_summary(
                        transcript, cfg.prompt_template, cfg.api_key, cfg.model
                    )
                )

                duration = int(self._recorder.elapsed_seconds) or 0
                meeting_id = self._app.db.create_meeting(
                    title=f"Встреча {time.strftime('%d.%m.%Y %H:%M')}",
                    date=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    duration=duration,
                    audio_path=str(audio_path) if audio_path else "",
                    transcript=transcript,
                    summary=summary,
                    prompt_used=cfg.prompt_template,
                )

                self.after(0, lambda: self._on_pipeline_done(meeting_id))
            except Exception:
                import traceback

                err_msg = traceback.format_exc()
                self.after(0, lambda: self._on_pipeline_error(err_msg))
            finally:
                loop.close()

        threading.Thread(target=run_pipeline, daemon=True).start()

    def _on_pipeline_done(self, meeting_id: int) -> None:
        """Обработка успешного завершения пайплайна."""
        self._rec_button.configure(
            state="normal",
            text="Начать запись",
            fg_color="#c0392b",
            hover_color="#e74c3c",
        )
        self._status_label.configure(text=f"Готово! Встреча #{meeting_id} сохранена.")
        self._app.set_status("Готово")
        self._mic_bar.set(0)
        self._sys_bar.set(0)
        self._timer_label.configure(text="00:00:00")
        # Переход к истории
        self._app.show_view("history")

    def _on_pipeline_error(self, error: str) -> None:
        """Обработка ошибки пайплайна."""
        self._rec_button.configure(
            state="normal",
            text="Начать запись",
            fg_color="#c0392b",
            hover_color="#e74c3c",
        )
        self._status_label.configure(text=f"Ошибка: {error}")
        self._app.set_status(f"Ошибка: {error}")

    def _on_audio_level(self, source: str, level: float) -> None:
        """Колбэк обновления индикатора уровня звука."""
        clamped = min(level * 10, 1.0)
        if source == "mic":
            self.after(0, lambda: self._mic_bar.set(clamped))
        else:
            self.after(0, lambda: self._sys_bar.set(clamped))

    def _update_timer(self) -> None:
        """Обновляет отображение таймера каждую секунду."""
        if not self._recorder.is_recording:
            return
        elapsed = int(self._recorder.elapsed_seconds)
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        self._timer_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.after(1000, self._update_timer)
