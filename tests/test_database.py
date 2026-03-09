from datetime import datetime
from src.storage.database import MeetingDB, Meeting

def test_create_and_get_meeting(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    meeting_id = db.create_meeting(
        title="Планёрка",
        date=datetime.now().isoformat(),
        duration=3600,
        audio_path="/tmp/test.wav",
        transcript="Обсуждали запуск",
        summary="# Протокол\n## Решения\n1. Запуск в апреле",
        prompt_used="default",
    )
    assert meeting_id == 1
    meeting = db.get_meeting(meeting_id)
    assert meeting.title == "Планёрка"
    assert meeting.duration == 3600
    db.close()

def test_list_meetings(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    db.create_meeting("Встреча 1", "2026-03-01", 1800, "", "", "", "")
    db.create_meeting("Встреча 2", "2026-03-02", 2400, "", "", "", "")
    meetings = db.list_meetings()
    assert len(meetings) == 2
    assert meetings[0].title == "Встреча 2"  # newest first
    db.close()

def test_search_meetings(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    db.create_meeting("Ретро", "2026-03-01", 1800, "", "спринт дизайн ревью", "", "")
    db.create_meeting("Планёрка", "2026-03-02", 1200, "", "бюджет финансы", "", "")
    results = db.search("дизайн")
    assert len(results) == 1
    assert results[0].title == "Ретро"
    db.close()

def test_update_meeting_title(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    mid = db.create_meeting("Без названия", "2026-03-01", 600, "", "", "", "")
    db.update_title(mid, "Стендап")
    meeting = db.get_meeting(mid)
    assert meeting.title == "Стендап"
    db.close()

def test_delete_meeting(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    mid = db.create_meeting("Удалить", "2026-03-01", 600, "", "", "", "")
    db.delete_meeting(mid)
    assert db.get_meeting(mid) is None
    db.close()


def test_create_folder(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    fid = db.create_folder("Проект А")
    folders = db.list_folders()
    assert len(folders) == 1
    assert folders[0]["id"] == fid
    assert folders[0]["name"] == "Проект А"
    assert folders[0]["parent_id"] is None
    db.close()

def test_create_subfolder(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    parent_id = db.create_folder("Проект А")
    child_id = db.create_folder("Спринт 1", parent_id=parent_id)
    folders = db.list_folders()
    assert len(folders) == 2
    child = [f for f in folders if f["id"] == child_id][0]
    assert child["parent_id"] == parent_id
    db.close()

def test_rename_folder(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    fid = db.create_folder("Старое")
    db.rename_folder(fid, "Новое")
    folders = db.list_folders()
    assert folders[0]["name"] == "Новое"
    db.close()

def test_delete_folder(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    fid = db.create_folder("Удалить")
    db.delete_folder(fid)
    assert db.list_folders() == []
    db.close()

def test_move_meeting_to_folder(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    fid = db.create_folder("Папка")
    mid = db.create_meeting(
        title="Тест", date="2026-01-01", duration=60,
        audio_path="", transcript="т", summary="с", prompt_used="п"
    )
    db.move_meeting(mid, fid)
    m = db.get_meeting(mid)
    assert m.folder_id == fid
    db.close()

def test_list_meetings_by_folder(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    fid = db.create_folder("Папка")
    db.create_meeting(
        title="В папке", date="2026-01-01", duration=60,
        audio_path="", transcript="", summary="", prompt_used=""
    )
    db.move_meeting(1, fid)
    db.create_meeting(
        title="Без папки", date="2026-01-02", duration=30,
        audio_path="", transcript="", summary="", prompt_used=""
    )
    in_folder = db.list_meetings(folder_id=fid, lightweight=True)
    assert len(in_folder) == 1
    assert in_folder[0].title == "В папке"
    all_meetings = db.list_meetings(lightweight=True)
    assert len(all_meetings) == 2
    db.close()

def test_update_summary(tmp_path):
    db = MeetingDB(tmp_path / "test.db")
    mid = db.create_meeting(
        title="Тест", date="2026-01-01", duration=60,
        audio_path="", transcript="текст", summary="старое", prompt_used="промпт1"
    )
    db.update_summary(mid, "новое саммари", "промпт2")
    m = db.get_meeting(mid)
    assert m.summary == "новое саммари"
    assert m.prompt_used == "промпт2"
    db.close()
