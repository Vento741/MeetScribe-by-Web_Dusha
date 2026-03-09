import numpy as np
import soundfile as sf
from src.audio.mixer import mix_audio

def test_mix_two_wav_files(tmp_path):
    sr = 44100
    duration = 2
    mic = np.random.randn(sr * duration, 1).astype(np.float32) * 0.5
    sys = np.random.randn(sr * duration, 1).astype(np.float32) * 0.5
    mic_path = tmp_path / "mic.wav"
    sys_path = tmp_path / "sys.wav"
    sf.write(str(mic_path), mic, sr)
    sf.write(str(sys_path), sys, sr)

    target_sr = 16000
    out = mix_audio(mic_path, sys_path, tmp_path / "mixed.wav")
    assert out.exists()
    data, rate = sf.read(str(out))
    assert rate == target_sr
    expected_len = int(duration * target_sr)
    assert abs(len(data) - expected_len) <= 1

def test_mix_single_file(tmp_path):
    sr = 44100
    audio = np.random.randn(sr, 1).astype(np.float32)
    mic_path = tmp_path / "mic.wav"
    sf.write(str(mic_path), audio, sr)

    out = mix_audio(mic_path, None, tmp_path / "mixed.wav")
    assert out.exists()
