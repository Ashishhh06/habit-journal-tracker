# journal/manager.py


import sqlite3
from datetime import datetime
from journal.db import get_connection
from journal.models import Entry, Habit
from journal.config import MOODS


class JournalManager:

    def add_entry(self, mood, note):
        if mood is not None and mood not in MOODS:
            raise ValueError(f"Invalid mood '{mood}'. Must be one of: {list(MOODS.keys())}")

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO entries (created_at, mood, note) VALUES (?, ?, ?)",
            (created_at, mood, note)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()

        return Entry(id=new_id, created_at=created_at, mood=mood, note=note)




    def add_habit(self, name):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO habits (name, active) VALUES (?, 1)",
                (name,)
            )
            conn.commit()
            new_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Habit '{name}' already exists.")
        conn.close()
        return Habit(id=new_id, name=name, active=1)

    def remove_habit(self, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE habits SET active = 0 WHERE name = ?", (name,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise ValueError(f"Habit '{name}' not found.")

    def list_active_habits(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, active FROM habits WHERE active = 1")
        rows = cursor.fetchall()
        conn.close()
        return [Habit(id=r[0], name=r[1], active=r[2]) for r in rows]

    def check_habit(self, name, date=None):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habits WHERE name = ? AND active = 1", (name,))
        row = cursor.fetchone()
        if row is None:
            conn.close()
            raise ValueError(f"Active habit '{name}' not found.")
        habit_id = row[0]

        cursor.execute(
            "INSERT OR REPLACE INTO habit_logs (habit_id, date, completed) VALUES (?, ?, 1)",
            (habit_id, date)
        )
        conn.commit()
        conn.close()





    def today_checklist(self, date=None):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.name, COALESCE(hl.completed, 0)
            FROM habits h
            LEFT JOIN habit_logs hl
                ON h.id = hl.habit_id AND hl.date = ?
            WHERE h.active = 1
            ORDER BY h.name
        """, (date,))
        rows = cursor.fetchall()
        conn.close()
        return rows  # list of (habit_name, completed) tuples