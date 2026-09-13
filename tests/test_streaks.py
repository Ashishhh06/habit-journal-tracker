# tests/test_streaks.py

from datetime import datetime, timedelta
from journal.streaks import compute_streaks, compute_weekly_streaks


def dates_ago(n_list):
    """Helper: convert a list of 'days ago' integers into date strings."""
    today = datetime.now().date()
    return [(today - timedelta(days=n)).strftime("%Y-%m-%d") for n in n_list]


def test_empty_list_returns_zero():
    assert compute_streaks([]) == (0, 0)


def test_compute_weekly_streaks():
    # Targets met: week 1, 2, 3. Week 4 missed.
    counts = [3, 3, 4, 1]
    targets = 3
    curr, longest = compute_weekly_streaks(counts, targets)
    assert curr == 0
    assert longest == 3
    
    # Target varying
    counts = [1, 2, 3]
    targets = [1, 2, 3]
    curr, longest = compute_weekly_streaks(counts, targets)
    assert curr == 3
    assert longest == 3


def test_single_day_today():
    current, longest = compute_streaks(dates_ago([0]))
    assert current == 1
    assert longest == 1


def test_consecutive_streak_ending_today():
    current, longest = compute_streaks(dates_ago([0, 1, 2, 3]))
    assert current == 4
    assert longest == 4


def test_streak_with_gap_breaks_current():
    # 5-day run from 6-2 days ago, then nothing yesterday, checked today
    current, longest = compute_streaks(dates_ago([6, 5, 4, 3, 2, 0]))
    assert longest == 5
    assert current == 1


def test_streak_alive_if_last_log_was_yesterday():
    # last logged yesterday, nothing today yet — streak should still be "alive"
    current, longest = compute_streaks(dates_ago([3, 2, 1]))
    assert current == 3
    assert longest == 3


def test_streak_dead_if_gap_of_two_days():
    # last logged 2 days ago — streak should be dead (current = 0)
    current, longest = compute_streaks(dates_ago([5, 4, 3, 2]))
    assert current == 0
    assert longest == 4