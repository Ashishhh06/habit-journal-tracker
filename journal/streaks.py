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

def compute_weekly_streaks(weekly_completion_counts, targets):
    """
    weekly_completion_counts: list of integers representing completions for consecutive weeks.
    targets: list of integers representing the target for each week, OR a single integer if the target is constant.
    Returns: (current_streak, longest_streak)
    """
    if not weekly_completion_counts:
        return 0, 0
        
    if isinstance(targets, int):
        targets = [targets] * len(weekly_completion_counts)
        
    longest = 0
    current_run = 0
    
    for count, target in zip(weekly_completion_counts, targets):
        if count >= target and target > 0:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 0
            
    # Assuming the list ends with the *current* week, if the current week isn't met yet,
    # the streak might be broken unless we handle "current week in progress".
    # For simplicity, if the last item didn't meet the target, current streak is 0.
    # In a real app we might look at the previous week if the current week isn't over.
    # We will just return current_run which is 0 if the last week failed, or > 0 if it succeeded.
    return current_run, longest