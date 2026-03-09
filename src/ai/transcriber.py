from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Callable

import soundfile as sf

from ai.openrouter_client import send_chat_request

logger = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = """Транскрибируй это аудио на русском языке.
Определи разных спикеров и обозначь их как "Спикер 1:", "Спикер 2:" и т.д.
Сохрани все высказывания дословно. Не пропускай ничего.
Если язык не русский, всё равно транскрибируй как есть.
Формат:
Спикер 1: текст
Спикер 2: текст
"""


def chunk_audio(
    wav_path: Path,
    chunk_minutes: int = 10,
    overlap_seconds: int = 30,
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


async def _transcribe_chunk(
    chunk_path: Path,
    api_key: str,
    model: str,
    semaphore: asyncio.Semaphore,
) -> str:
    """Транскрибирует один чанк аудио."""
    async with semaphore:
        file_size_mb = chunk_path.stat().st_size / (1024 * 1024)
        logger.info("Транскрибация чанка: %s (%.1f MB)", chunk_path.name, file_size_mb)
        audio_b64 = _audio_to_base64(chunk_path)
        messages = [
            {
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
            }
        ]
        return await send_chat_request(messages, api_key, model, timeout=300)


async def transcribe_audio(
    wav_path: Path,
    api_key: str,
    model: str = "google/gemini-3.1-flash-lite-preview",
    progress_callback: Callable | None = None,
) -> str:
    """Транскрибирует аудиофайл через OpenRouter API с параллельной обработкой чанков."""
    chunks = chunk_audio(wav_path)

    if len(chunks) == 1:
        text = await _transcribe_chunk(chunks[0], api_key, model, asyncio.Semaphore(1))
        if progress_callback:
            progress_callback(1.0)
        return text

    semaphore = asyncio.Semaphore(3)
    tasks = [
        _transcribe_chunk(chunk_path, api_key, model, semaphore)
        for chunk_path in chunks
    ]
    transcripts = await asyncio.gather(*tasks)

    if progress_callback:
        progress_callback(1.0)

    return "\n\n".join(transcripts)
