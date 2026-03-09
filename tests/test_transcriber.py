import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from src.ai.transcriber import transcribe_audio, chunk_audio

def test_chunk_audio(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 44100
    # 25 мин аудио → должно быть 3 чанка (10+10+5) с перекрытием
    audio = np.random.randn(sr * 60 * 25).astype(np.float32)
    wav_path = tmp_path / "long.wav"
    sf.write(str(wav_path), audio, sr)
    chunks = chunk_audio(wav_path, chunk_minutes=10, overlap_seconds=30)
    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk.exists()

def test_chunk_short_audio(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 44100
    audio = np.random.randn(sr * 60 * 5).astype(np.float32)
    wav_path = tmp_path / "short.wav"
    sf.write(str(wav_path), audio, sr)
    chunks = chunk_audio(wav_path, chunk_minutes=10)
    assert len(chunks) == 1
    assert chunks[0] == wav_path

@pytest.mark.asyncio
async def test_transcribe_audio_calls_api(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 44100
    audio = np.random.randn(sr * 5).astype(np.float32)
    wav_path = tmp_path / "test.wav"
    sf.write(str(wav_path), audio, sr)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Спикер 1: Привет\nСпикер 2: Здравствуйте"}}]
    }

    with patch("src.ai.transcriber.httpx.AsyncClient") as MockClient:
        client = AsyncMock()
        client.post.return_value = mock_response
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await transcribe_audio(wav_path, api_key="test-key", model="test-model")
        assert "Спикер 1" in result
        assert "Привет" in result
