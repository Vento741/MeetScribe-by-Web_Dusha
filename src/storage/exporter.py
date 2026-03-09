from __future__ import annotations

import logging
import re
from pathlib import Path

from src.storage.database import Meeting

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Очищает имя файла от недопустимых символов."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()[:50]


def _format_duration(seconds: int) -> str:
    """Форматирует длительность в ЧЧ:ММ:СС."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def export_to_markdown(meeting: Meeting, output_dir: Path) -> Path:
    """Экспортирует встречу в Markdown-файл."""
    output_dir.mkdir(parents=True, exist_ok=True)
    date_part = meeting.date[:10]
    title_part = _sanitize_filename(meeting.title or "meeting")
    filename = f"{date_part}_{title_part}.md"
    path = output_dir / filename

    content = meeting.summary or ""
    if not content:
        content = (
            f"# {meeting.title}\n\n"
            f"**Дата:** {meeting.date}\n"
            f"**Длительность:** {_format_duration(meeting.duration)}\n\n"
            f"## Транскрипт\n\n{meeting.transcript}"
        )

    path.write_text(content, encoding="utf-8")
    logger.info("Экспортирована встреча %d в %s", meeting.id, path)
    return path
