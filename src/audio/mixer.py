from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Простое пересемплирование через линейную интерполяцию."""
    if orig_sr == target_sr:
        return data
    ratio = target_sr / orig_sr
    new_len = int(len(data) * ratio)
    indices = np.linspace(0, len(data) - 1, new_len)
    if data.ndim == 1:
        return np.interp(indices, np.arange(len(data)), data).astype(np.float32)
    # Многоканальный
    result = np.zeros((new_len, data.shape[1]), dtype=np.float32)
    for ch in range(data.shape[1]):
        result[:, ch] = np.interp(indices, np.arange(len(data)), data[:, ch])
    return result


def mix_audio(
    mic_path: Path | None,
    sys_path: Path | None,
    output_path: Path,
    target_sr: int = 16000,
) -> Path:
    """Микширует аудио с микрофона и системного звука в один файл."""
    streams = []

    for path in (mic_path, sys_path):
        if path and path.exists():
            data, rate = sf.read(str(path), dtype="float32")
            if data.ndim == 1:
                data = data.reshape(-1, 1)
            # Пересемплирование к целевой частоте
            data = _resample(data, rate, target_sr)
            streams.append(data)

    if not streams:
        raise ValueError("Нет аудиофайлов для микширования")

    if len(streams) == 1:
        mixed = streams[0]
    else:
        d1, d2 = streams[0], streams[1]
        # Дополняем короткий трек до длины длинного
        max_len = max(len(d1), len(d2))
        if len(d1) < max_len:
            d1 = np.pad(d1, ((0, max_len - len(d1)), (0, 0)))
        if len(d2) < max_len:
            d2 = np.pad(d2, ((0, max_len - len(d2)), (0, 0)))
        # Сведение в моно
        d1_mono = d1.mean(axis=1) if d1.ndim > 1 else d1
        d2_mono = d2.mean(axis=1) if d2.ndim > 1 else d2
        mixed = (d1_mono + d2_mono) / 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), mixed, target_sr)
    logger.info("Микшированное аудио сохранено: %s (sr=%d)", output_path, target_sr)
    return output_path
