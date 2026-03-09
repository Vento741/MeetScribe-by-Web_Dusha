from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


def mix_audio(
    mic_path: Path | None,
    sys_path: Path | None,
    output_path: Path,
) -> Path:
    """Микширует аудио с микрофона и системного звука в один файл."""
    streams = []
    sr = 44100

    for path in (mic_path, sys_path):
        if path and path.exists():
            data, rate = sf.read(str(path), dtype="float32")
            if data.ndim == 1:
                data = data.reshape(-1, 1)
            streams.append((data, rate))
            sr = rate

    if not streams:
        raise ValueError("Нет аудиофайлов для микширования")

    if len(streams) == 1:
        mixed = streams[0][0]
    else:
        d1, d2 = streams[0][0], streams[1][0]
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
    sf.write(str(output_path), mixed, sr)
    logger.info("Микшированное аудио сохранено: %s", output_path)
    return output_path
