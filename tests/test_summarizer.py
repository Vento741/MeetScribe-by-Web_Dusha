import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ai.summarizer import generate_summary

@pytest.mark.asyncio
async def test_generate_summary():
    transcript = "Спикер 1: Запускаем MVP в апреле\nСпикер 2: Согласен"
    prompt = "Создай протокол встречи"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "# Протокол\n## Решения\n1. Запуск MVP в апреле"}}]
    }

    with patch("src.ai.summarizer.httpx.AsyncClient") as MockClient:
        client = AsyncMock()
        client.post.return_value = mock_response
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await generate_summary(transcript, prompt, api_key="key", model="model")
        assert "Протокол" in result
        assert "MVP" in result
