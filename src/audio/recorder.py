from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger(__name__)


@dataclass
class AudioDevice:
    """Аудиоустройство системы."""
    index: int
    name: str
    channels: int
    is_loopback: bool


def list_audio_devices() -> list[AudioDevice]:
    """Возвращает список доступных аудиоустройств ввода."""
    devices = []
    all_devs = sd.query_devices()
    hostapis = sd.query_hostapis()

    for i, dev in enumerate(all_devs):
        if dev["max_input_channels"] > 0:
            api_name = hostapis[dev["hostapi"]]["name"] if dev["hostapi"] < len(hostapis) else ""
            is_loopback = "loopback" in dev["name"].lower() or "wasapi" in api_name.lower()
            devices.append(AudioDevice(
                index=i,
                name=dev["name"],
                channels=dev["max_input_channels"],
                is_loopback=is_loopback,
            ))
    return devices


class AudioRecorder:
    """Записывает аудио с микрофона и системного звука одновременно."""

    def __init__(self) -> None:
        self.is_recording: bool = False
        self._mic_thread: threading.Thread | None = None
        self._sys_thread: threading.Thread | None = None
        self._mic_data: list[np.ndarray] = []
        self._sys_data: list[np.ndarray] = []
        self._mic_path: Path | None = None
        self._sys_path: Path | None = None
        self._start_time: float = 0
        self._level_callback: Callable | None = None

    @property
    def elapsed_seconds(self) -> float:
        """Возвращает прошедшее время записи в секундах."""
        if not self.is_recording:
            return 0
        return time.time() - self._start_time

    def set_level_callback(self, callback: Callable) -> None:
        """Устанавливает колбэк для уровня громкости."""
        self._level_callback = callback

    def _record_stream(
        self, device: int, data_list: list, samplerate: int = 44100, channels: int = 1, is_mic: bool = True,
    ) -> None:
        """Записывает аудиопоток с указанного устройства."""
        try:
            def callback(indata, frames, time_info, status):
                if status:
                    logger.warning("Статус аудио (%s): %s", "микрофон" if is_mic else "система", status)
                data_list.append(indata.copy())
                if self._level_callback:
                    level = float(np.abs(indata).mean())
                    self._level_callback("mic" if is_mic else "sys", level)

            with sd.InputStream(device=device, samplerate=samplerate,
                                channels=channels, callback=callback):
                while self.is_recording:
                    sd.sleep(100)
        except Exception as e:
            logger.error("Ошибка записи (%s): %s", "микрофон" if is_mic else "система", e)

    def start(
        self, output_dir: Path, mic_device: int | None = None,
        loopback_device: int | None = None,
    ) -> None:
        """Начинает запись с указанных устройств."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._mic_path = output_dir / f"mic_{timestamp}.wav"
        self._sys_path = output_dir / f"sys_{timestamp}.wav"
        self._mic_data = []
        self._sys_data = []
        self.is_recording = True
        self._start_time = time.time()

        if mic_device is not None:
            self._mic_thread = threading.Thread(
                target=self._record_stream,
                args=(mic_device, self._mic_data),
                kwargs={"is_mic": True},
                daemon=True,
            )
            self._mic_thread.start()

        if loopback_device is not None:
            self._sys_thread = threading.Thread(
                target=self._record_stream,
                args=(loopback_device, self._sys_data),
                kwargs={"is_mic": False},
                daemon=True,
            )
            self._sys_thread.start()

    def stop(self) -> tuple[Path | None, Path | None]:
        """Останавливает запись и сохраняет WAV-файлы."""
        self.is_recording = False

        if self._mic_thread:
            self._mic_thread.join(timeout=3)
        if self._sys_thread:
            self._sys_thread.join(timeout=3)

        mic_path = self._save_wav(self._mic_data, self._mic_path)
        sys_path = self._save_wav(self._sys_data, self._sys_path)

        return mic_path, sys_path

    def _save_wav(self, data: list[np.ndarray], path: Path | None) -> Path | None:
        """Сохраняет записанные данные в WAV-файл."""
        if not data or path is None:
            return None
        try:
            audio = np.concatenate(data, axis=0)
            sf.write(str(path), audio, samplerate=44100)
            logger.info("Аудио сохранено: %s (%.1f сек)", path, len(audio) / 44100)
            return path
        except Exception as e:
            logger.error("Не удалось сохранить WAV %s: %s", path, e)
            return None
