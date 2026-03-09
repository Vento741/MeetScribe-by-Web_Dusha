from src.storage.database import Meeting
from src.storage.exporter import (
    export_to_markdown, export_to_txt, export_to_html, export_to_pdf,
)

def test_export_creates_md_file(tmp_path):
    meeting = Meeting(
        id=1, title="Тест", date="2026-03-09T10:00:00",
        duration=3600, audio_path="", transcript="Транскрипт тут",
        summary="# Протокол\n## Решения\n1. Тест", prompt_used="",
        created_at="2026-03-09",
    )
    path = export_to_markdown(meeting, tmp_path)
    assert path.exists()
    assert path.suffix == ".md"
    content = path.read_text(encoding="utf-8")
    assert "Тест" in content
    assert "Протокол" in content

def test_export_filename_format(tmp_path):
    meeting = Meeting(
        id=1, title="Планёрка", date="2026-03-09T14:30:00",
        duration=1800, audio_path="", transcript="", summary="Саммари",
        prompt_used="", created_at="2026-03-09",
    )
    path = export_to_markdown(meeting, tmp_path)
    assert "2026-03-09" in path.name
    assert "Планёрка" in path.name


def test_export_to_txt(tmp_path):
    m = Meeting(id=1, title="Тест", date="2026-01-01", duration=60,
                audio_path="", transcript="транскрипт", summary="# Саммари\n\n- Пункт 1",
                prompt_used="", created_at="")
    path = export_to_txt(m, tmp_path)
    assert path.exists()
    assert path.suffix == ".txt"
    text = path.read_text(encoding="utf-8")
    assert "Саммари" in text
    assert "#" not in text  # markdown stripped


def test_export_to_html(tmp_path):
    m = Meeting(id=1, title="Тест", date="2026-01-01", duration=60,
                audio_path="", transcript="транскрипт", summary="# Саммари\n\n- Пункт 1",
                prompt_used="", created_at="")
    path = export_to_html(m, tmp_path)
    assert path.exists()
    assert path.suffix == ".html"
    html = path.read_text(encoding="utf-8")
    assert "<h1>" in html or "<h1" in html


def test_export_to_pdf(tmp_path):
    m = Meeting(id=1, title="Тест PDF", date="2026-01-01", duration=60,
                audio_path="", transcript="транскрипт",
                summary="# Протокол\n\n## Резюме\n\nТекст резюме\n\n- Пункт 1\n- Пункт 2",
                prompt_used="", created_at="")
    path = export_to_pdf(m, tmp_path)
    assert path.exists()
    assert path.suffix == ".pdf"
    assert path.stat().st_size > 100  # не пустой
