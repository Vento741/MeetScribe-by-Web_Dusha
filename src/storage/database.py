from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Meeting:
    id: int
    title: str
    date: str
    duration: int
    audio_path: str
    transcript: str
    summary: str
    prompt_used: str
    created_at: str
    folder_id: int | None = None


class MeetingDB:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS folders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                parent_id  INTEGER REFERENCES folders(id) ON DELETE CASCADE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS meetings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT,
                date        TEXT NOT NULL,
                duration    INTEGER,
                audio_path  TEXT,
                transcript  TEXT,
                summary     TEXT,
                prompt_used TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                folder_id   INTEGER REFERENCES folders(id) ON DELETE SET NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS meetings_fts USING fts5(
                title, transcript, summary,
                content='meetings', content_rowid='id'
            );
            CREATE TRIGGER IF NOT EXISTS meetings_ai AFTER INSERT ON meetings BEGIN
                INSERT INTO meetings_fts(rowid, title, transcript, summary)
                VALUES (new.id, new.title, new.transcript, new.summary);
            END;
            CREATE TRIGGER IF NOT EXISTS meetings_ad AFTER DELETE ON meetings BEGIN
                INSERT INTO meetings_fts(meetings_fts, rowid, title, transcript, summary)
                VALUES ('delete', old.id, old.title, old.transcript, old.summary);
            END;
            CREATE TRIGGER IF NOT EXISTS meetings_au AFTER UPDATE ON meetings BEGIN
                INSERT INTO meetings_fts(meetings_fts, rowid, title, transcript, summary)
                VALUES ('delete', old.id, old.title, old.transcript, old.summary);
                INSERT INTO meetings_fts(rowid, title, transcript, summary)
                VALUES (new.id, new.title, new.transcript, new.summary);
            END;
        """)
        # Миграция: добавить folder_id если таблица уже существует без неё
        try:
            self._conn.execute("SELECT folder_id FROM meetings LIMIT 1")
        except sqlite3.OperationalError:
            self._conn.execute(
                "ALTER TABLE meetings ADD COLUMN folder_id INTEGER "
                "REFERENCES folders(id) ON DELETE SET NULL"
            )
            self._conn.commit()

    def _row_to_meeting(self, row: sqlite3.Row) -> Meeting:
        d = dict(row)
        if "folder_id" not in d:
            d["folder_id"] = None
        return Meeting(**d)

    def create_meeting(
        self,
        title: str,
        date: str,
        duration: int,
        audio_path: str,
        transcript: str,
        summary: str,
        prompt_used: str,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO meetings (title, date, duration, audio_path, transcript, summary, prompt_used) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, date, duration, audio_path, transcript, summary, prompt_used),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_meeting(self, meeting_id: int) -> Meeting | None:
        row = self._conn.execute(
            "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()
        return self._row_to_meeting(row) if row else None

    def list_meetings(
        self, lightweight: bool = False, folder_id: int | None = None
    ) -> list[Meeting]:
        if lightweight:
            base = (
                "SELECT id, title, date, duration, audio_path, '' as transcript, "
                "'' as summary, '' as prompt_used, created_at, folder_id "
                "FROM meetings"
            )
        else:
            base = "SELECT * FROM meetings"
        if folder_id is not None:
            base += " WHERE folder_id = ?"
            rows = self._conn.execute(
                base + " ORDER BY date DESC", (folder_id,)
            ).fetchall()
        else:
            rows = self._conn.execute(base + " ORDER BY date DESC").fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def search(self, query: str, lightweight: bool = False) -> list[Meeting]:
        if lightweight:
            cols = (
                "m.id, m.title, m.date, m.duration, m.audio_path, "
                "'' as transcript, '' as summary, '' as prompt_used, m.created_at, m.folder_id"
            )
        else:
            cols = "m.*"
        rows = self._conn.execute(
            f"SELECT {cols} FROM meetings m "
            "JOIN meetings_fts f ON m.id = f.rowid "
            "WHERE meetings_fts MATCH ? ORDER BY rank",
            (query,),
        ).fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def update_title(self, meeting_id: int, title: str) -> None:
        self._conn.execute(
            "UPDATE meetings SET title = ? WHERE id = ?", (title, meeting_id)
        )
        self._conn.commit()

    def delete_meeting(self, meeting_id: int) -> None:
        row = self._conn.execute(
            "SELECT audio_path FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()
        if row and row["audio_path"]:
            p = Path(row["audio_path"])
            if p.exists():
                p.unlink()
        self._conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        self._conn.commit()

    def create_folder(self, name: str, parent_id: int | None = None) -> int:
        """Create a new folder and return its id."""
        cursor = self._conn.execute(
            "INSERT INTO folders (name, parent_id) VALUES (?, ?)",
            (name, parent_id),
        )
        self._conn.commit()
        return cursor.lastrowid

    def list_folders(self) -> list[dict]:
        """Return all folders ordered by name."""
        rows = self._conn.execute(
            "SELECT id, name, parent_id, created_at FROM folders ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

    def rename_folder(self, folder_id: int, name: str) -> None:
        """Rename a folder."""
        self._conn.execute(
            "UPDATE folders SET name = ? WHERE id = ?", (name, folder_id)
        )
        self._conn.commit()

    def delete_folder(self, folder_id: int) -> None:
        """Delete a folder. Meetings in this folder get folder_id set to NULL."""
        self._conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        self._conn.commit()

    def move_meeting(self, meeting_id: int, folder_id: int | None) -> None:
        """Move a meeting into a folder (or out of any folder if None)."""
        self._conn.execute(
            "UPDATE meetings SET folder_id = ? WHERE id = ?",
            (folder_id, meeting_id),
        )
        self._conn.commit()

    def update_summary(self, meeting_id: int, summary: str, prompt_used: str) -> None:
        """Update the summary and prompt_used for a meeting."""
        self._conn.execute(
            "UPDATE meetings SET summary = ?, prompt_used = ? WHERE id = ?",
            (summary, prompt_used, meeting_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
