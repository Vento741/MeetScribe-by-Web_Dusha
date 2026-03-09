import json
from pathlib import Path
from src.config import AppConfig, load_config, save_config

def test_default_config():
    cfg = AppConfig()
    assert cfg.model == "google/gemini-3.1-flash-lite-preview"
    assert cfg.theme == "dark"
    assert cfg.language == "ru"
    assert cfg.hotkey_toggle == "ctrl+shift+r"

def test_save_and_load_config(tmp_path):
    cfg = AppConfig(api_key="test-key-123", theme="light")
    config_path = tmp_path / "config.json"
    save_config(cfg, config_path)
    loaded = load_config(config_path)
    assert loaded.api_key == "test-key-123"
    assert loaded.theme == "light"

def test_load_missing_config_returns_default(tmp_path):
    config_path = tmp_path / "nonexistent.json"
    cfg = load_config(config_path)
    assert cfg.api_key == ""
    assert cfg.model == "google/gemini-3.1-flash-lite-preview"

def test_config_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key-456")
    cfg = load_config(tmp_path / "nonexistent.json")
    assert cfg.api_key == "env-key-456"
