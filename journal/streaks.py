# journal/streaks.py

from datetime import datetime, timedelta


def compute_streaks(logged_dates):
    """
    logged_dates: a list/set of date strings 'YYYY-MM-DD' where the habit was completed.
    Returns: (current_streak, longest_streak)
    """
    if not logged_dates:
        return 0, 0

    dates = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in set(logged_dates))

    longest = 1
    current_run = 1

    for i in range(1, len(dates)):
        if dates[i] == dates[i - 1] + timedelta(days=1):
            current_run += 1
        else:
            current_run = 1
        longest = max(longest, current_run)

    today = datetime.now().date()
    last_date = dates[-1]

    if last_date == today or last_date == today - timedelta(days=1):
        current_streak = current_run if last_date == dates[-1] else 0
        streak_end = dates[-1]
        streak_len = 1
        i = len(dates) - 1
        while i > 0 and dates[i] == dates[i - 1] + timedelta(days=1):
            streak_len += 1
            i -= 1
        current_streak = streak_len
    else:
        current_streak = 0

    return current_streak, longest