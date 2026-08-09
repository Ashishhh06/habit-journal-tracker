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
    def __init__(self, id=None, user_id=None, name=None, active=1):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.active = active

    def __repr__(self):
        return f"Habit(id={self.id}, user_id={self.user_id}, name={self.name!r}, active={self.active})"



class User:
    def __init__(self, id=None, username=None, password_hash=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    def __repr__(self):
        return f"User(id={self.id}, username={self.username!r})"