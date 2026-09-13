# journal/models.py
class Entry:
    def __init__(self, id=None, user_id=None, created_at=None, mood=None, note=None):
        self.id = id
        self.user_id = user_id
        self.created_at = created_at
        self.mood = mood
        self.note = note

    def __repr__(self):
        return f"Entry(id={self.id}, user_id={self.user_id}, created_at={self.created_at}, mood={self.mood!r}, note={self.note!r})"


class Habit:
    def __init__(self, id=None, user_id=None, name=None, active=1, category=None, emoji=None, color=None, frequency_type='daily', weekly_target=None):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.active = active
        self.category = category
        self.emoji = emoji
        self.color = color
        self.frequency_type = frequency_type
        self.weekly_target = weekly_target

    def __repr__(self):
        return f"Habit(id={self.id}, user_id={self.user_id}, name={self.name!r}, active={self.active}, freq={self.frequency_type})"



class User:
    def __init__(self, id=None, username=None, password_hash=None, email=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email

    def __repr__(self):
        return f"User(id={self.id}, username={self.username!r}, email={self.email!r})"