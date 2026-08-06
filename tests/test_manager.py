# tests/test_manager.py

import pytest
import journal.db as db_module
from journal.manager import JournalManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """Provides a JournalManager backed by a fresh, temporary SQLite file per test."""
    test_db_path = tmp_path / "test_habit_tracker.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db_path))

    db_module.init_db()
    return JournalManager()


def test_add_entry_returns_entry_with_id(manager):
    entry = manager.add_entry(mood="happy", note="Test note")
    assert entry.id is not None
    assert entry.mood == "happy"
    assert entry.note == "Test note"


def test_add_entry_rejects_invalid_mood(manager):
    with pytest.raises(ValueError):
        manager.add_entry(mood="furious", note="Not a real mood")


def test_add_habit_and_list_active(manager):
    manager.add_habit("Workout")
    manager.add_habit("Read")
    habits = manager.list_active_habits()
    names = [h.name for h in habits]
    assert "Workout" in names
    assert "Read" in names


def test_add_duplicate_habit_raises_error(manager):
    manager.add_habit("Workout")
    with pytest.raises(ValueError):
        manager.add_habit("Workout")


def test_remove_habit_hides_from_active_list(manager):
    manager.add_habit("Workout")
    manager.remove_habit("Workout")
    habits = manager.list_active_habits()
    names = [h.name for h in habits]
    assert "Workout" not in names


def test_remove_nonexistent_habit_raises_error(manager):
    with pytest.raises(ValueError):
        manager.remove_habit("DoesNotExist")


def test_check_habit_marks_completed_today(manager):
    manager.add_habit("Workout")
    manager.check_habit("Workout")
    checklist = manager.today_checklist()
    result = dict(checklist)
    assert result["Workout"] == 1


def test_check_habit_twice_same_day_does_not_error(manager):
    manager.add_habit("Workout")
    manager.check_habit("Workout")
    manager.check_habit("Workout")  # should not raise
    checklist = manager.today_checklist()
    assert dict(checklist)["Workout"] == 1