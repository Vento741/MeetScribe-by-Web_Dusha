from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Callable

import httpx
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

TRANSCRIPTION_PROMPT = """Транскрибируй это аудио на русском языке.
Определи разных спикеров и обозначь их как "Спикер 1:", "Спикер 2:" и т.д.
Сохрани все высказывания дословно. Не пропускай ничего.
Если язык не русский, всё равно транскрибируй как есть.
Формат:
Спикер 1: текст
Спикер 2: текст
"""


def chunk_audio(
    wav_path: Path, chunk_minutes: int = 10, overlap_seconds: int = 30,
) -> list[Path]:
    """Разбивает аудиофайл на чанки заданной длительности с перекрытием."""
    data, sr = sf.read(str(wav_path), dtype="float32")
    total_samples = len(data)
    chunk_samples = chunk_minutes * 60 * sr
    overlap_samples = overlap_seconds * sr

    if total_samples <= chunk_samples:
        return [wav_path]

    chunks: list[Path] = []
    start = 0
    idx = 0
    while start < total_samples:
        end = min(start + chunk_samples, total_samples)
        chunk_data = data[start:end]
        chunk_path = wav_path.parent / f"{wav_path.stem}_chunk{idx}{wav_path.suffix}"
        sf.write(str(chunk_path), chunk_data, sr)
        chunks.append(chunk_path)
        idx += 1
        start = end - overlap_samples if end < total_samples else total_samples

    logger.info("Разбито %s на %d чанков", wav_path, len(chunks))
    return chunks


def _audio_to_base64(wav_path: Path) -> str:
    """Кодирует WAV-файл в base64."""
    return base64.b64encode(wav_path.read_bytes()).decode("utf-8")


async def transcribe_audio(
    wav_path: Path,
    api_key: str,
    model: str = "google/gemini-3.1-flash-lite-preview",
    progress_callback: Callable | None = None,
) -> str:
    """Транскрибирует аудиофайл через OpenRouter API с разбивкой на чанки."""
    chunks = chunk_audio(wav_path)
    transcripts: list[str] = []

    async with httpx.AsyncClient(timeout=300) as client:
        for i, chunk_path in enumerate(chunks):
            audio_b64 = _audio_to_base64(chunk_path)

            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": TRANSCRIPTION_PROMPT},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_b64,
                                "format": "wav",
                            },
                        },
                    ],
                }],
            }

            for attempt in range(3):
                try:
                    resp = await client.post(
                        OPENROUTER_URL,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    text = result["choices"][0]["message"]["content"]
                    transcripts.append(text)
                    if progress_callback:
                        progress_callback((i + 1) / len(chunks))
                    break
                except (httpx.HTTPStatusError, httpx.RequestError, KeyError) as e:
                    logger.warning("Попытка транскрибации %d не удалась: %s", attempt + 1, e)
                    if attempt == 2:
                        raise

    return "\n\n".join(transcripts)
