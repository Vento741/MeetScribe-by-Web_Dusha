import pytest
from unittest.mock import patch, MagicMock
from src.audio.recorder import AudioRecorder, list_audio_devices

def test_list_audio_devices():
    mock_pyaudio_instance = MagicMock()
    mock_pyaudio_instance.get_loopback_device_info_generator.return_value = [
        {"index": 25, "name": "Speakers [Loopback]", "maxInputChannels": 2, "defaultSampleRate": 48000.0},
    ]
    mock_pyaudio_instance.get_default_wasapi_loopback.return_value = {"index": 25}

    with patch("src.audio.recorder.sd") as mock_sd, \
         patch("src.audio.recorder.pyaudio.PyAudio", return_value=mock_pyaudio_instance):
        # WASAPI host API at index 0, default input device = 0
        mock_sd.query_hostapis.side_effect = lambda idx=None: (
            [{"name": "Windows WASAPI", "default_input_device": 0}]
            if idx is None
            else {"name": "Windows WASAPI", "default_input_device": 0}
        )
        mock_sd.query_devices.return_value = [
            {"name": "Mic", "max_input_channels": 2, "max_output_channels": 0, "hostapi": 0},
        ]
        devices = list_audio_devices()
        assert len(devices) == 2
        assert devices[0].is_loopback is False
        assert devices[0].name == "Mic"
        assert devices[0].is_default is True
        assert devices[1].is_loopback is True
        assert devices[1].name == "Speakers [Loopback]"
        assert devices[1].is_default is True

def test_recorder_init():
    recorder = AudioRecorder()
    assert recorder.is_recording is False

def test_recorder_start_stop(tmp_path):
    with patch("src.audio.recorder.sd"), \
         patch("src.audio.recorder.pyaudio"):
        recorder = AudioRecorder()
        recorder.start(output_dir=tmp_path, mic_device=0, loopback_device=25)
        assert recorder.is_recording is True
        mic_path, sys_path = recorder.stop()
        assert recorder.is_recording is False
