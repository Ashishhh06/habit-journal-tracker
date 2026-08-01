# journal/models.py

class Entry:
    def __init__(self, id=None, created_at=None, mood=None, note=None):
        self.id = id
        self.created_at = created_at
        self.mood = mood
        self.note = note

    def __repr__(self):
        return f"Entry(id={self.id}, created_at={self.created_at}, mood={self.mood!r}, note={self.note!r})"


class Habit:
    def __init__(self, id=None, name=None, active=1):
        self.id = id
        self.name = name
        self.active = active

    def __repr__(self):
        return f"Habit(id={self.id}, name={self.name!r}, active={self.active})"