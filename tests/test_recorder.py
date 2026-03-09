import pytest
from unittest.mock import patch, MagicMock
from src.audio.recorder import AudioRecorder, list_audio_devices

def test_list_audio_devices():
    with patch("src.audio.recorder.sd") as mock_sd:
        mock_sd.query_devices.return_value = [
            {"name": "Mic", "max_input_channels": 2, "hostapi": 0},
            {"name": "Speakers (loopback)", "max_input_channels": 2, "hostapi": 0},
        ]
        mock_sd.query_hostapis.return_value = [{"name": "Windows WASAPI"}]
        devices = list_audio_devices()
        assert len(devices) >= 1

def test_recorder_init():
    recorder = AudioRecorder()
    assert recorder.is_recording is False

def test_recorder_start_stop(tmp_path):
    with patch("src.audio.recorder.sd") as mock_sd:
        mock_sd.query_devices.return_value = {
            "name": "Test", "default_samplerate": 44100, "max_input_channels": 2
        }
        recorder = AudioRecorder()
        recorder.start(output_dir=tmp_path, mic_device=0, loopback_device=1)
        assert recorder.is_recording is True
        mic_path, sys_path = recorder.stop()
        assert recorder.is_recording is False
