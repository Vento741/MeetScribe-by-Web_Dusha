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


class MeetingDB:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS meetings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT,
                date        TEXT NOT NULL,
                duration    INTEGER,
                audio_path  TEXT,
                transcript  TEXT,
                summary     TEXT,
                prompt_used TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
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

    def _row_to_meeting(self, row: sqlite3.Row) -> Meeting:
        return Meeting(**dict(row))

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

    def list_meetings(self) -> list[Meeting]:
        rows = self._conn.execute(
            "SELECT * FROM meetings ORDER BY date DESC"
        ).fetchall()
        return [self._row_to_meeting(r) for r in rows]

    def search(self, query: str) -> list[Meeting]:
        rows = self._conn.execute(
            "SELECT m.* FROM meetings m "
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
        self._conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
