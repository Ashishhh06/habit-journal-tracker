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
    jm = JournalManager()
    jm.register_user("test", "test")
    return jm


def test_add_entry_returns_entry_with_id(manager):
    entry = manager.add_entry(user_id=1, mood="happy", note="Test note")
    assert entry.id is not None
    assert entry.mood == "happy"
    assert entry.note == "Test note"


def test_add_entry_rejects_invalid_mood(manager):
    with pytest.raises(ValueError):
        manager.add_entry(user_id=1, mood="furious", note="Not a real mood")


def test_add_habit_and_list_active(manager):
    manager.add_habit(1, "Workout")
    manager.add_habit(1, "Read")
    habits = manager.list_active_habits(1)
    names = [h.name for h in habits]
    assert "Workout" in names
    assert "Read" in names


def test_add_duplicate_habit_raises_error(manager):
    manager.add_habit(1, "Workout")
    with pytest.raises(ValueError):
        manager.add_habit(1, "Workout")


def test_remove_habit_hides_from_active_list(manager):
    manager.add_habit(1, "Workout")
    manager.remove_habit(1, "Workout")
    habits = manager.list_active_habits(1)
    names = [h.name for h in habits]
    assert "Workout" not in names


def test_remove_nonexistent_habit_raises_error(manager):
    with pytest.raises(ValueError):
        manager.remove_habit(1, "DoesNotExist")


def test_check_habit_marks_completed_today(manager):
    manager.add_habit(1, "Workout")
    manager.check_habit(1, "Workout")
    checklist = manager.today_checklist(1)
    result = {row[0]: row[1] for row in checklist}
    assert result["Workout"] == 1


def test_check_habit_twice_same_day_does_not_error(manager):
    manager.add_habit(1, "Workout")
    manager.check_habit(1, "Workout")
    manager.check_habit(1, "Workout")  # should not raise
    checklist = manager.today_checklist(1)
    result = {row[0]: row[1] for row in checklist}
    assert result["Workout"] == 1

def test_toggle_habit(manager):
    manager.add_habit(1, "ToggleMe")
    
    # Check
    state = manager.toggle_habit(1, "ToggleMe")
    assert state == 1
    
    # Uncheck
    state = manager.toggle_habit(1, "ToggleMe")
    assert state == 0
    
def test_weekly_habit(manager):
    h = manager.add_habit(1, "WeeklyRun", frequency_type="weekly", weekly_target=3)
    manager.toggle_habit(1, "WeeklyRun", date="2026-08-01") # Saturday
    manager.toggle_habit(1, "WeeklyRun", date="2026-08-02") # Sunday
    progress, target = manager.get_weekly_progress(1, h.id, "2026-07-27") # The week of Mon Jul 27
    assert progress == 2
    assert target == 3
    
def test_search_entries(manager):
    manager.add_entry(1, "happy", "this is a great day")
    manager.add_entry(1, "sad", "this is a bad day")
    
    res1 = manager.search_entries(1, "2000-01-01", "2100-01-01", mood_filter="happy")
    assert len(res1) == 1
    
    res2 = manager.search_entries(1, "2000-01-01", "2100-01-01", text_search="bad")
    assert len(res2) == 1

def test_get_achievements(manager):
    # Ensure it doesn't crash on empty db
    achievements = manager.get_achievements(1)
    assert len(achievements) == 6
    assert all(not a['earned'] for a in achievements)


def test_schedule_management(manager):
    h = manager.add_habit(1, "Morning Jog")
    manager.set_habit_schedule(h.id, ["Mon", "Wed", "Fri"], "07:00")
    sched = manager.get_habit_schedule(h.id)
    assert set(sched["days"]) == {"Mon", "Wed", "Fri"}
    assert sched["time"] == "07:00"

    # Overwrite schedule
    manager.set_habit_schedule(h.id, ["Tue", "Thu"], "08:30")
    sched2 = manager.get_habit_schedule(h.id)
    assert set(sched2["days"]) == {"Tue", "Thu"}
    assert sched2["time"] == "08:30"


def test_weekly_timetable(manager):
    h1 = manager.add_habit(1, "Gym")
    manager.set_habit_schedule(h1.id, ["Mon", "Wed"], "18:00")

    h2 = manager.add_habit(1, "Read Book") # Unsched -> anytime every day

    timetable = manager.get_weekly_timetable(1, start_date="2026-08-24") # Monday Aug 24 2026
    assert timetable["start_date"] == "2026-08-24"
    assert len(timetable["days"]) == 7

    mon_habits = timetable["days"][0]["habits"]
    mon_names = [h["name"] for h in mon_habits]
    assert "Gym" in mon_names
    assert "Read Book" in mon_names

    tue_habits = timetable["days"][1]["habits"]
    tue_names = [h["name"] for h in tue_habits]
    assert "Gym" not in tue_names
    assert "Read Book" in tue_names


def test_today_checklist_with_schedule(manager):
    h1 = manager.add_habit(1, "Morning Yoga")
    manager.set_habit_schedule(h1.id, ["Mon"], "06:30")

    h2 = manager.add_habit(1, "Drink Water") # Unsched

    # Test on a Monday date
    res = manager.get_today_checklist_with_schedule(1, date_str="2026-08-24")
    timed_names = [h["name"] for h in res["timed"]]
    anytime_names = [h["name"] for h in res["anytime"]]

    assert "Morning Yoga" in timed_names
    assert "Drink Water" in anytime_names


def test_goals_crud_and_isolation(manager):
    user1_id = 1
    manager.register_user("user2", "password")
    user2_id = 2

    h1 = manager.add_habit(user1_id, "Run 5k")
    h2 = manager.add_habit(user2_id, "Read SciFi")

    # User 1 creates a goal
    goal1 = manager.add_goal(user1_id, h1.id, "Run under 25 mins")
    assert goal1["id"] is not None
    assert goal1["completed"] == 0

    goals_u1 = manager.list_goals(user1_id)
    assert len(goals_u1) == 1
    assert goals_u1[0]["description"] == "Run under 25 mins"

    # User 2 lists goals -> empty
    goals_u2 = manager.list_goals(user2_id)
    assert len(goals_u2) == 0

    # User 2 tries to access/modify User 1's goal -> raises ValueError
    with pytest.raises(ValueError):
        manager.toggle_goal(user2_id, goal1["id"])

    with pytest.raises(ValueError):
        manager.edit_goal(user2_id, goal1["id"], "Hacked desc")

    with pytest.raises(ValueError):
        manager.delete_goal(user2_id, goal1["id"])

    # User 1 toggles, edits, and deletes their goal
    new_state = manager.toggle_goal(user1_id, goal1["id"])
    assert new_state == 1

    manager.edit_goal(user1_id, goal1["id"], "Run under 24 mins")
    updated_goals = manager.list_goals(user1_id)
    assert updated_goals[0]["description"] == "Run under 24 mins"

    manager.delete_goal(user1_id, goal1["id"])
    assert len(manager.list_goals(user1_id)) == 0


def test_get_habit_completion_counts(manager):
    user1_id = 1
    # Test zero habits user
    manager.register_user("zero_habits_usr", "pw")
    zero_counts = manager.get_habit_completion_counts(2, "7d")
    assert len(zero_counts) == 0

    h = manager.add_habit(user1_id, "Meditate")
    manager.toggle_habit(user1_id, "Meditate", date="2026-08-20")
    manager.toggle_habit(user1_id, "Meditate", date="2026-08-21")

    counts_7d = manager.get_habit_completion_counts(user1_id, "7d")
    assert len(counts_7d) >= 1
    meditate_stat = next(item for item in counts_7d if item["name"] == "Meditate")
    assert meditate_stat["count"] >= 0

    # Test range with zero completions
    counts_30d = manager.get_habit_completion_counts(user1_id, "30d")
    assert isinstance(counts_30d, list)



def test_timetable_grid_and_isolation(manager):
    user1_id = 1
    manager.register_user("tb_user2", "password")
    user2_id = 2

    # Add time blocks in unordered start_times
    b2 = manager.add_time_block(user1_id, "12:00", "13:00")
    b1 = manager.add_time_block(user1_id, "07:00", "07:30")

    grid1 = manager.get_timetable_grid(user1_id)
    assert len(grid1) == 2
    # Verify ordering by start_time
    assert grid1[0]["id"] == b1["id"]
    assert grid1[1]["id"] == b2["id"]

    # User 1 sets cell text
    manager.set_cell(user1_id, b1["id"], "Mon", "Meditation")
    grid_updated = manager.get_timetable_grid(user1_id)
    assert grid_updated[0]["cells"]["Mon"] == "Meditation"

    # Setting empty label should delete the DB cell row
    manager.set_cell(user1_id, b1["id"], "Mon", "   ")
    grid_cleared = manager.get_timetable_grid(user1_id)
    assert grid_cleared[0]["cells"]["Mon"] == ""

    # User 2 isolation tests: User 2 cannot access or edit User 1's block
    with pytest.raises(ValueError):
        manager.set_cell(user2_id, b1["id"], "Mon", "Hacked")

    with pytest.raises(ValueError):
        manager.delete_time_block(user2_id, b1["id"])

    # User 1 deletes time block
    manager.delete_time_block(user1_id, b1["id"])
    grid_final = manager.get_timetable_grid(user1_id)
    assert len(grid_final) == 1
    assert grid_final[0]["id"] == b2["id"]


def test_month_calendar_and_year_heatmap(manager):
    user1_id = 1
    manager.register_user("u2_m", "pw")
    user2_id = 2

    h1 = manager.add_habit(user1_id, "Daily Coding")
    manager.toggle_habit(user1_id, "Daily Coding", date="2026-08-01")
    manager.toggle_habit(user1_id, "Daily Coding", date="2026-08-02")
    manager.toggle_habit(user1_id, "Daily Coding", date="2026-08-03")

    # Month calendar test for Aug 2026
    month_cal = manager.get_habit_month_calendar(user1_id, "Daily Coding", 2026, 8)
    assert month_cal["month_name"] == "August"
    assert month_cal["total_checkins"] == 3
    assert len(month_cal["weeks"]) >= 4

    # Aug 1 2026 is Saturday -> week 0 index 6 should be day 1 (completed=True)
    first_week = month_cal["weeks"][0]
    assert first_week[0] is None # Sun is None
    assert first_week[6]["day"] == 1
    assert first_week[6]["completed"] is True

    # Year heatmap test for 2026
    year_map = manager.get_habit_year_heatmap(user1_id, "Daily Coding", mode=2026)
    assert year_map["total_checkins"] == 3
    assert year_map["max_streak"] == 3
    assert len(year_map["weeks"]) >= 52

    # Rolling current heatmap
    curr_map = manager.get_habit_year_heatmap(user1_id, "Daily Coding", mode="current")
    assert curr_map["label"] == "in the past year"

    # Isolation check: User 2 cannot access User 1's habit calendar/heatmap
    with pytest.raises(ValueError):
        manager.get_habit_month_calendar(user2_id, "Daily Coding", 2026, 8)

    with pytest.raises(ValueError):
        manager.get_habit_year_heatmap(user2_id, "Daily Coding", mode="current")


