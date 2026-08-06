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



    def get_mood_trend(self, start_date, end_date):
        import pandas as pd
        from journal.config import MOODS

        conn = get_connection()
        entries_df = pd.read_sql_query("""
            SELECT created_at, mood
            FROM entries
            WHERE date(created_at) BETWEEN ? AND ? AND mood IS NOT NULL
        """, conn, params=(start_date, end_date))
        conn.close()

        if entries_df.empty:
            return pd.Series(dtype=float)

        entries_df["date"] = pd.to_datetime(entries_df["created_at"]).dt.strftime("%Y-%m-%d")
        entries_df["score"] = entries_df["mood"].map(MOODS)

        daily_avg = entries_df.groupby("date")["score"].mean()
        return daily_avg

    def plot_mood_trend(self, start_date, end_date, save_path="mood_trend.png"):
        import matplotlib.pyplot as plt

        daily_avg = self.get_mood_trend(start_date, end_date)

        fig, ax = plt.subplots(figsize=(max(6, len(daily_avg) * 0.5), 3))

        if daily_avg.empty:
            ax.text(0.5, 0.5, "No mood data in this range", ha="center", va="center")
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            ax.plot(daily_avg.index, daily_avg.values, marker="o", color="#1565c0", linewidth=2)
            ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
            ax.set_ylim(-2.5, 2.5)
            ax.set_ylabel("Mood score")
            plt.xticks(rotation=45, ha="right")

        ax.set_title(f"Mood Trend: {start_date} to {end_date}")
        fig.tight_layout()
        fig.savefig(save_path, dpi=150)
        plt.close(fig)

        return save_path





    def generate_monthly_dashboard(self, year, month, save_path="monthly_dashboard.png"):
        import matplotlib.pyplot as plt
        import calendar

        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"

        matrix = self.get_habit_matrix(start_date, end_date)
        mood_avg = self.get_mood_trend(start_date, end_date)

        if matrix.empty or len(matrix.index) == 0:
            daily_pct = [0] * len(matrix.columns)
        else:
            daily_pct = (matrix.sum(axis=0) / len(matrix.index)) * 100

        fig, axes = plt.subplots(
            3, 1, figsize=(max(10, last_day * 0.4), 10),
            gridspec_kw={"height_ratios": [len(matrix.index) or 1, 2, 2]}
        )
        fig.suptitle(f"Monthly Report: {calendar.month_name[month]} {year}", fontsize=16, fontweight="bold")

        ax1 = axes[0]
        im = ax1.imshow(matrix.values, cmap="Greens", vmin=0, vmax=1, aspect="auto")
        ax1.set_yticks(range(len(matrix.index)))
        ax1.set_yticklabels(matrix.index)
        ax1.set_xticks(range(len(matrix.columns)))
        ax1.set_xticklabels(matrix.columns, rotation=90, fontsize=7)
        ax1.set_title("Habit Completion")

        ax2 = axes[1]
        ax2.plot(matrix.columns, daily_pct, marker="o", color="#2e7d32", linewidth=2)
        ax2.fill_between(matrix.columns, daily_pct, color="#2e7d32", alpha=0.15)
        ax2.set_ylim(0, 105)
        ax2.set_ylabel("Completion %")
        ax2.set_xticks(range(len(matrix.columns)))
        ax2.set_xticklabels([])
        ax2.set_title("Daily Completion %")

        ax3 = axes[2]
        if not mood_avg.empty:
            ax3.plot(mood_avg.index, mood_avg.values, marker="o", color="#1565c0", linewidth=2)
        ax3.axhline(0, color="gray", linewidth=0.8, linestyle="--")
        ax3.set_ylim(-2.5, 2.5)
        ax3.set_ylabel("Mood score")
        ax3.set_xticks(range(len(matrix.columns)))
        ax3.set_xticklabels(matrix.columns, rotation=90, fontsize=7)
        ax3.set_title("Mood Trend")

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        fig.savefig(save_path, dpi=150)
        plt.close(fig)

        return save_path