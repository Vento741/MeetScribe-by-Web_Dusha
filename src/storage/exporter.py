from __future__ import annotations

import logging
import re
from pathlib import Path

import markdown as md_lib
from fpdf import FPDF

from storage.database import Meeting

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Очищает имя файла от недопустимых символов."""
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()[:50]


def format_duration(seconds: int) -> str:
    """Форматирует длительность в ЧЧ:ММ:СС."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _get_export_path(meeting: Meeting, output_dir: Path, ext: str) -> Path:
    """Возвращает путь для экспортируемого файла."""
    output_dir.mkdir(parents=True, exist_ok=True)
    date_part = meeting.date[:10]
    title_part = _sanitize_filename(meeting.title or "meeting")
    return output_dir / f"{date_part}_{title_part}.{ext}"


def _get_content(meeting: Meeting) -> str:
    """Возвращает контент для экспорта (саммари или fallback)."""
    if meeting.summary:
        return meeting.summary
    return (
        f"# {meeting.title}\n\n"
        f"**Дата:** {meeting.date}\n"
        f"**Длительность:** {format_duration(meeting.duration)}\n\n"
        f"## Транскрипт\n\n{meeting.transcript}"
    )


def export_to_markdown(meeting: Meeting, output_dir: Path) -> Path:
    """Экспортирует встречу в Markdown-файл."""
    path = _get_export_path(meeting, output_dir, "md")
    content = _get_content(meeting)
    path.write_text(content, encoding="utf-8")
    logger.info("Экспортирована встреча %d в %s", meeting.id, path)
    return path


def export_to_txt(meeting: Meeting, output_dir: Path) -> Path:
    """Экспортирует встречу в текстовый файл (без markdown-разметки)."""
    path = _get_export_path(meeting, output_dir, "txt")
    content = _get_content(meeting)
    # Убираем markdown-разметку
    text = re.sub(r"#{1,6}\s*", "", content)  # заголовки
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # жирный
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # курсив
    text = re.sub(r"^\s*[-*]\s+", "  • ", text, flags=re.MULTILINE)  # списки
    text = re.sub(r"\|", " ", text)  # таблицы → пробелы
    text = re.sub(r"-{3,}", "", text)  # разделители таблиц
    path.write_text(text.strip(), encoding="utf-8")
    logger.info("Экспортировано TXT: %s", path)
    return path


def export_to_html(meeting: Meeting, output_dir: Path) -> Path:
    """Экспортирует встречу в HTML-файл."""
    path = _get_export_path(meeting, output_dir, "html")
    content = _get_content(meeting)
    body = md_lib.markdown(content, extensions=["tables"])
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{meeting.title or "Протокол встречи"}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
h2 {{ color: #444; margin-top: 24px; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
th {{ background: #f5f5f5; font-weight: bold; }}
ul, ol {{ padding-left: 24px; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
    logger.info("Экспортировано HTML: %s", path)
    return path


def export_to_pdf(meeting: Meeting, output_dir: Path) -> Path:
    """Экспортирует встречу в PDF-файл с кириллицей."""
    path = _get_export_path(meeting, output_dir, "pdf")
    content = _get_content(meeting)

    pdf = FPDF()
    pdf.add_page()
    # Используем Arial из Windows (поддерживает кириллицу)
    fonts_dir = Path("C:/Windows/Fonts")
    pdf.add_font("Arial", "", fname=str(fonts_dir / "arial.ttf"))
    pdf.add_font("Arial", "B", fname=str(fonts_dir / "arialbd.ttf"))
    pdf.set_font("Arial", size=11)

    lm = pdf.l_margin

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
            continue

        # Сбрасываем X на левый отступ перед каждой строкой
        pdf.x = lm

        # Заголовки
        if stripped.startswith("# "):
            pdf.set_font("Arial", "B", size=18)
            pdf.cell(0, 10, stripped[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            pdf.set_font("Arial", size=11)
        elif stripped.startswith("## "):
            pdf.set_font("Arial", "B", size=14)
            pdf.cell(0, 8, stripped[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            pdf.set_font("Arial", size=11)
        elif stripped.startswith("### "):
            pdf.set_font("Arial", "B", size=12)
            pdf.cell(0, 7, stripped[4:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            pdf.set_font("Arial", size=11)
        # Маркированные списки
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:]
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
            pdf.multi_cell(0, 6, f"  -  {text}")
        # Нумерованные списки
        elif re.match(r"^\d+\.\s", stripped):
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            pdf.multi_cell(0, 6, text)
        # Таблица — разделительная строка (пропускаем)
        elif re.match(r"^\|[-\s|]+\|$", stripped):
            continue
        # Таблица — строка с данными
        elif stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            col_w = (pdf.w - lm - pdf.r_margin) / max(len(cells), 1)
            for cell_text in cells:
                cell_text = re.sub(r"\*\*(.+?)\*\*", r"\1", cell_text)
                pdf.cell(col_w, 7, cell_text, border=1)
            pdf.ln()
        # Обычный текст
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            text = re.sub(r"\*(.+?)\*", r"\1", text)
            pdf.multi_cell(0, 6, text)

    pdf.output(str(path))
    logger.info("Экспортировано PDF: %s", path)
    return path
