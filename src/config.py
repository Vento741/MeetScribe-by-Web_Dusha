from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = """На основе транскрипта встречи создай структурированный протокол на русском языке:

# Протокол встречи

## Краткое резюме
(2-3 предложения об основных итогах)

## Ключевые темы обсуждения
(маркированный список)

## Принятые решения
(нумерованный список)

## Action Items
| Ответственный | Задача | Срок |
|---------------|--------|------|
(таблица)

## Открытые вопросы
(маркированный список)

## Позиции участников
(кто какую позицию занял по ключевым вопросам)
"""

def _default_save_dir() -> str:
    return str(Path.home() / "Documents" / "MeetScribe")

def _default_appdata_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "MeetScribe"


@dataclass
class AppConfig:
    api_key: str = ""
    model: str = "google/gemini-3.1-flash-lite-preview"
    theme: str = "dark"
    hotkey_toggle: str = "ctrl+shift+r"
    hotkey_export: str = "ctrl+shift+s"
    save_dir: str = field(default_factory=_default_save_dir)
    prompt_template: str = field(default_factory=lambda: DEFAULT_PROMPT)
    language: str = "ru"
    mic_device: int | None = None
    loopback_device: int | None = None

    @property
    def appdata_dir(self) -> Path:
        return _default_appdata_dir()

    @property
    def db_path(self) -> Path:
        return self.appdata_dir / "meetings.db"

    @property
    def config_path(self) -> Path:
        return self.appdata_dir / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    if path is None:
        path = _default_appdata_dir() / "config.json"

    cfg = AppConfig()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, value)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load config from %s: %s", path, e)

    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        cfg.api_key = env_key

    return cfg


def save_config(cfg: AppConfig, path: Path | None = None) -> None:
    if path is None:
        path = cfg.config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
