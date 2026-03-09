from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def generate_summary(
    transcript: str,
    prompt_template: str,
    api_key: str,
    model: str = "google/gemini-3.1-flash-lite-preview",
) -> str:
    """Генерирует структурированное саммари встречи по транскрипту."""
    messages = [
        {"role": "system", "content": prompt_template},
        {"role": "user", "content": f"Вот транскрипт встречи:\n\n{transcript}"},
    ]

    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    OPENROUTER_URL,
                    json={"model": model, "messages": messages},
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                return result["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError) as e:
                logger.warning(
                    "Попытка генерации саммари %d не удалась: %s", attempt + 1, e
                )
                if attempt == 2:
                    raise

    return ""
