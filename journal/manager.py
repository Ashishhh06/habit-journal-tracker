# journal/manager.py


import sqlite3
from datetime import datetime
from journal.db import get_connection
from journal.models import Entry, Habit
from journal.config import MOODS
from journal.streaks import compute_streaks


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




    def get_habit_streaks(self, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habits WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row is None:
            conn.close()
            raise ValueError(f"Habit '{name}' not found.")
        habit_id = row[0]

        cursor.execute(
            "SELECT date FROM habit_logs WHERE habit_id = ? AND completed = 1",
            (habit_id,)
        )
        dates = [r[0] for r in cursor.fetchall()]
        conn.close()

        return compute_streaks(dates)


    
    def view_range(self, start_date, end_date):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, mood, note
            FROM entries
            WHERE date(created_at) BETWEEN ? AND ?
            ORDER BY created_at
        """, (start_date, end_date))
        entries = [Entry(id=r[0], created_at=r[1], mood=r[2], note=r[3]) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT h.name, hl.date
            FROM habit_logs hl
            JOIN habits h ON h.id = hl.habit_id
            WHERE hl.date BETWEEN ? AND ? AND hl.completed = 1
            ORDER BY hl.date
        """, (start_date, end_date))
        habit_completions = cursor.fetchall()

        conn.close()
        return entries, habit_completions



    def get_habit_matrix(self, start_date, end_date):
        import pandas as pd

        conn = get_connection()
        habits_df = pd.read_sql_query(
            "SELECT id, name FROM habits WHERE active = 1", conn
        )
        logs_df = pd.read_sql_query("""
            SELECT habit_id, date, completed
            FROM habit_logs
            WHERE date BETWEEN ? AND ? AND completed = 1
        """, conn, params=(start_date, end_date))
        conn.close()

        date_range = pd.date_range(start=start_date, end=end_date).strftime("%Y-%m-%d")
        matrix = pd.DataFrame(0, index=habits_df["name"], columns=date_range)

        for _, row in logs_df.iterrows():
            habit_name = habits_df.loc[habits_df["id"] == row["habit_id"], "name"]
            if not habit_name.empty:
                matrix.loc[habit_name.values[0], row["date"]] = 1

        return matrix



    def plot_habit_heatmap(self, start_date, end_date, save_path="habit_heatmap.png"):
        import matplotlib.pyplot as plt

        matrix = self.get_habit_matrix(start_date, end_date)

        fig, ax = plt.subplots(figsize=(max(6, len(matrix.columns) * 0.6), max(2, len(matrix.index) * 0.6)))
        im = ax.imshow(matrix.values, cmap="Greens", vmin=0, vmax=1, aspect="auto")

        ax.set_xticks(range(len(matrix.columns)))
        ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(matrix.index)))
        ax.set_yticklabels(matrix.index)

        ax.set_title(f"Habit Completion: {start_date} to {end_date}")
        fig.tight_layout()
        fig.savefig(save_path, dpi=150)
        plt.close(fig)

        return save_path


    def plot_completion_trend(self, start_date, end_date, save_path="completion_trend.png"):
        import matplotlib.pyplot as plt

        matrix = self.get_habit_matrix(start_date, end_date)

        if matrix.empty or len(matrix.index) == 0:
            daily_pct = [0] * len(matrix.columns)
        else:
            daily_pct = (matrix.sum(axis=0) / len(matrix.index)) * 100

        fig, ax = plt.subplots(figsize=(max(6, len(matrix.columns) * 0.5), 3))
        ax.plot(matrix.columns, daily_pct, marker="o", color="#2e7d32", linewidth=2)
        ax.fill_between(matrix.columns, daily_pct, color="#2e7d32", alpha=0.15)

        ax.set_ylim(0, 105)
        ax.set_ylabel("Completion %")
        ax.set_title(f"Daily Habit Completion: {start_date} to {end_date}")
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        fig.savefig(save_path, dpi=150)
        plt.close(fig)

        return save_path