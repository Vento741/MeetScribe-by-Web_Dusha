from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pyaudiowpatch as pyaudio
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
    is_default: bool = False


def _get_wasapi_host_api_index() -> int | None:
    """Возвращает индекс WASAPI host API в sounddevice."""
    for i, api in enumerate(sd.query_hostapis()):
        if "wasapi" in api["name"].lower():
            return i
    return None


def list_audio_devices() -> list[AudioDevice]:
    """Возвращает список микрофонов (только WASAPI) и loopback-устройств."""
    devices = []

    # Определяем дефолтное устройство ввода системы
    wasapi_idx = _get_wasapi_host_api_index()
    default_input = None
    if wasapi_idx is not None:
        api_info = sd.query_hostapis(wasapi_idx)
        default_input = api_info.get("default_input_device")

    # Микрофоны через sounddevice — только WASAPI host API
    all_devs = sd.query_devices()
    for i, dev in enumerate(all_devs):
        if dev["max_input_channels"] > 0 and dev.get("hostapi") == wasapi_idx:
            devices.append(
                AudioDevice(
                    index=i,
                    name=dev["name"],
                    channels=dev["max_input_channels"],
                    is_loopback=False,
                    is_default=(i == default_input),
                )
            )

    # WASAPI loopback через pyaudiowpatch
    try:
        p = pyaudio.PyAudio()
        try:
            loopback_list = list(p.get_loopback_device_info_generator())
            # Определяем дефолтный loopback (соответствует дефолтному выходу)
            default_loopback_idx = None
            try:
                default_out = p.get_default_wasapi_loopback()
                default_loopback_idx = default_out["index"]
            except Exception:
                pass

            for dev in loopback_list:
                devices.append(
                    AudioDevice(
                        index=dev["index"],
                        name=dev["name"],
                        channels=dev["maxInputChannels"],
                        is_loopback=True,
                        is_default=(dev["index"] == default_loopback_idx),
                    )
                )
        finally:
            p.terminate()
    except Exception as e:
        logger.warning("Не удалось получить loopback-устройства: %s", e)

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
        self._elapsed: float = 0
        self._level_callback: Callable | None = None
        self._sys_samplerate: int = 48000
        self._barrier: threading.Barrier | None = None
        self.mic_error: str | None = None
        self.sys_error: str | None = None
        # Время первого сэмпла для выравнивания дорожек
        self._mic_first_sample_time: float = 0
        self._sys_first_sample_time: float = 0
        self._rec_start_time: float = 0  # общая точка отсчёта

    @property
    def elapsed_seconds(self) -> float:
        """Возвращает прошедшее время записи в секундах."""
        if self.is_recording:
            return time.time() - self._start_time
        return self._elapsed

    def set_level_callback(self, callback: Callable) -> None:
        """Устанавливает колбэк для уровня громкости."""
        self._level_callback = callback

    def _record_mic(self, device: int, data_list: list) -> None:
        """Записывает аудио с микрофона через sounddevice."""
        try:
            dev_info = sd.query_devices(device)
            channels = min(dev_info["max_input_channels"], 1) or 1
            samplerate = int(dev_info["default_samplerate"])
            self._mic_samplerate = samplerate
            logger.info(
                "Микрофон: device=%d, sr=%d, ch=%d, name=%s",
                device,
                samplerate,
                channels,
                dev_info["name"],
            )

            recording_active = threading.Event()
            first_sample_recorded = threading.Event()

            def callback(indata, frames, time_info, status):
                if not recording_active.is_set():
                    return
                if not first_sample_recorded.is_set():
                    self._mic_first_sample_time = time.time()
                    first_sample_recorded.set()
                if status:
                    logger.warning("Статус аудио (микрофон): %s", status)
                data_list.append(indata.copy())
                if self._level_callback:
                    level = float(np.abs(indata).mean())
                    self._level_callback("mic", level)

            with sd.InputStream(
                device=device,
                samplerate=samplerate,
                channels=channels,
                callback=callback,
            ):
                if self._barrier:
                    self._barrier.wait(timeout=5)
                recording_active.set()
                while self.is_recording:
                    sd.sleep(100)
        except Exception as e:
            self.mic_error = str(e)
            logger.error("Ошибка записи (микрофон): %s", e)

    def _record_loopback(self, device: int, data_list: list) -> None:
        """Записывает системный звук через pyaudiowpatch WASAPI loopback.

        Использует callback-режим, чтобы непрерывно получать данные
        (включая тишину, когда нет системного звука). Это гарантирует
        временную синхронизацию с микрофонной дорожкой.
        """
        p = pyaudio.PyAudio()
        try:
            dev_info = p.get_device_info_by_index(device)
            channels = dev_info["maxInputChannels"]
            samplerate = int(dev_info["defaultSampleRate"])
            self._sys_samplerate = samplerate

            CHUNK = 1024
            recording_active = threading.Event()
            first_sample_recorded = threading.Event()

            def callback(in_data, frame_count, time_info, status):
                if not recording_active.is_set():
                    return (None, pyaudio.paContinue)
                if not first_sample_recorded.is_set():
                    self._sys_first_sample_time = time.time()
                    first_sample_recorded.set()
                audio = np.frombuffer(in_data, dtype=np.float32).reshape(-1, channels)
                data_list.append(audio)
                if self._level_callback:
                    level = float(np.abs(audio).mean())
                    self._level_callback("sys", level)
                return (None, pyaudio.paContinue)

            stream = p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=samplerate,
                input=True,
                input_device_index=device,
                frames_per_buffer=CHUNK,
                stream_callback=callback,
            )

            if self._barrier:
                self._barrier.wait(timeout=5)

            recording_active.set()
            stream.start_stream()

            while self.is_recording:
                time.sleep(0.1)

            stream.stop_stream()
            stream.close()
        except Exception as e:
            self.sys_error = str(e)
            logger.error("Ошибка записи (система): %s", e)
        finally:
            p.terminate()

    def start(
        self,
        output_dir: Path,
        mic_device: int | None = None,
        loopback_device: int | None = None,
    ) -> None:
        """Начинает запись с указанных устройств."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._mic_path = output_dir / f"mic_{timestamp}.wav"
        self._sys_path = output_dir / f"sys_{timestamp}.wav"
        self._mic_data = []
        self._sys_data = []
        self._mic_samplerate: int = 44100
        self.mic_error = None
        self.sys_error = None
        self._mic_first_sample_time = 0
        self._sys_first_sample_time = 0
        self.is_recording = True
        self._start_time = time.time()
        self._rec_start_time = self._start_time

        parties = sum(1 for d in (mic_device, loopback_device) if d is not None)
        self._barrier = threading.Barrier(parties) if parties > 1 else None

        if mic_device is not None:
            self._mic_thread = threading.Thread(
                target=self._record_mic,
                args=(mic_device, self._mic_data),
                daemon=True,
            )
            self._mic_thread.start()

        if loopback_device is not None:
            self._sys_thread = threading.Thread(
                target=self._record_loopback,
                args=(loopback_device, self._sys_data),
                daemon=True,
            )
            self._sys_thread.start()

    def stop(self) -> tuple[Path | None, Path | None]:
        """Останавливает запись и сохраняет WAV-файлы."""
        self._elapsed = time.time() - self._start_time
        self.is_recording = False

        if self._mic_thread:
            self._mic_thread.join(timeout=3)
        if self._sys_thread:
            self._sys_thread.join(timeout=3)

        # Вычисляем смещение каждой дорожки от начала записи
        mic_offset = (
            self._mic_first_sample_time - self._rec_start_time
            if self._mic_first_sample_time > 0
            else 0
        )
        sys_offset = (
            self._sys_first_sample_time - self._rec_start_time
            if self._sys_first_sample_time > 0
            else 0
        )

        logger.info(
            "Смещения дорожек: mic=%.2f сек, sys=%.2f сек",
            mic_offset,
            sys_offset,
        )

        mic_path = self._save_wav(
            self._mic_data, self._mic_path, self._mic_samplerate, mic_offset
        )
        sys_path = self._save_wav(
            self._sys_data, self._sys_path, self._sys_samplerate, sys_offset
        )

        return mic_path, sys_path

    def _save_wav(
        self,
        data: list[np.ndarray],
        path: Path | None,
        samplerate: int = 44100,
        offset_seconds: float = 0,
    ) -> Path | None:
        """Сохраняет записанные данные в WAV-файл.

        Если offset_seconds > 0, в начало добавляется тишина для
        выравнивания дорожки по общей временной шкале записи.
        """
        if not data or path is None:
            return None
        try:
            audio = np.concatenate(data, axis=0)
            channels = audio.shape[1] if audio.ndim > 1 else 1

            # Паддинг тишиной в начале для выравнивания
            if offset_seconds > 0.05:  # игнорируем мелкие рассинхронизации < 50мс
                silence_samples = int(offset_seconds * samplerate)
                if audio.ndim > 1:
                    silence = np.zeros(
                        (silence_samples, channels), dtype=np.float32
                    )
                else:
                    silence = np.zeros(silence_samples, dtype=np.float32)
                audio = np.concatenate([silence, audio], axis=0)
                logger.info(
                    "Добавлена тишина %.2f сек (%d сэмплов) в начало %s",
                    offset_seconds,
                    silence_samples,
                    path.name,
                )

            sf.write(str(path), audio, samplerate=samplerate)
            logger.info(
                "Аудио сохранено: %s (%.1f сек)", path, len(audio) / samplerate
            )
            return path
        except Exception as e:
            logger.error("Не удалось сохранить WAV %s: %s", path, e)
            return None
