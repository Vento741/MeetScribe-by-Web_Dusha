from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RETRIES = 3


async def send_chat_request(
    messages: list[dict[str, Any]],
    api_key: str,
    model: str,
    timeout: int = 120,
) -> str:
    """Отправляет запрос к OpenRouter API с повторными попытками."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(MAX_RETRIES):
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
                content = result["choices"][0]["message"]["content"]
                logger.info(
                    "API ответ: model=%s, длина=%d символов",
                    result.get("model", "?"),
                    len(content) if content else 0,
                )
                return content or ""
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError) as e:
                logger.warning("Попытка %d не удалась: %s", attempt + 1, e)
                if attempt == MAX_RETRIES - 1:
                    raise

    return ""
