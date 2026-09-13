# journal/db.py

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "habit_tracker.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE
        )
    """)

    # Migration for existing DBs
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE")
    except sqlite3.OperationalError:
        pass  # Column already exists


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            mood TEXT,
            note TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            category TEXT,
            emoji TEXT,
            color TEXT,
            frequency_type TEXT DEFAULT 'daily',
            weekly_target INTEGER,
            UNIQUE(user_id, name)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            completed INTEGER NOT NULL,
            FOREIGN KEY (habit_id) REFERENCES habits(id),
            UNIQUE(habit_id, date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            time TEXT,
            FOREIGN KEY (habit_id) REFERENCES habits(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (habit_id) REFERENCES habits(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable_cells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            label TEXT NOT NULL,
            FOREIGN KEY (block_id) REFERENCES timetable_blocks(id),
            UNIQUE(block_id, day_of_week)
        )
    """)

    conn.commit()
    
    # Phase 3 Migrations for existing habits table
    columns_to_add = [
        "category TEXT",
        "emoji TEXT",
        "color TEXT",
        "frequency_type TEXT DEFAULT 'daily'",
        "weekly_target INTEGER"
    ]
    for col_def in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE habits ADD COLUMN {col_def}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.close()
if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")