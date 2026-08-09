# journal/manager.py

import sqlite3
import os
from datetime import datetime
from journal.db import get_connection
from journal.models import Entry, Habit, User
from journal.config import MOODS
from journal.streaks import compute_streaks


class JournalManager:

    # ---------- User accounts ----------

    def register_user(self, username, password):
        from werkzeug.security import generate_password_hash

        password_hash = generate_password_hash(password)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
            conn.commit()
            new_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Username '{username}' is already taken.")
        conn.close()
        return User(id=new_id, username=username, password_hash=password_hash)

    def get_user_by_username(self, username):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return User(id=row[0], username=row[1], password_hash=row[2])

    def get_user_by_id(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return User(id=row[0], username=row[1], password_hash=row[2])

    def verify_password(self, user, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(user.password_hash, password)

    # ---------- Journal entries ----------

    def add_entry(self, user_id, mood, note):
        if mood is not None and mood not in MOODS:
            raise ValueError(f"Invalid mood '{mood}'. Must be one of: {list(MOODS.keys())}")

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO entries (user_id, created_at, mood, note) VALUES (?, ?, ?, ?)",
            (user_id, created_at, mood, note)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()

        return Entry(id=new_id, user_id=user_id, created_at=created_at, mood=mood, note=note)

    def view_range(self, user_id, start_date, end_date):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, created_at, mood, note
            FROM entries
            WHERE date(created_at) BETWEEN ? AND ? AND user_id = ?
            ORDER BY created_at
        """, (start_date, end_date, user_id))
        entries = [Entry(id=r[0], user_id=r[1], created_at=r[2], mood=r[3], note=r[4]) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT h.name, hl.date
            FROM habit_logs hl
            JOIN habits h ON h.id = hl.habit_id
            WHERE hl.date BETWEEN ? AND ? AND hl.completed = 1 AND h.user_id = ?
            ORDER BY hl.date
        """, (start_date, end_date, user_id))
        habit_completions = cursor.fetchall()

        conn.close()
        return entries, habit_completions

    # ---------- Habits ----------

    def add_habit(self, user_id, name):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO habits (user_id, name, active) VALUES (?, ?, 1)",
                (user_id, name)
            )
            conn.commit()
            new_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Habit '{name}' already exists.")
        conn.close()
        return Habit(id=new_id, user_id=user_id, name=name, active=1)

    def remove_habit(self, user_id, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE habits SET active = 0 WHERE name = ? AND user_id = ?",
            (name, user_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        if affected == 0:
            raise ValueError(f"Habit '{name}' not found.")

    def list_active_habits(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, name, active FROM habits WHERE active = 1 AND user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [Habit(id=r[0], user_id=r[1], name=r[2], active=r[3]) for r in rows]

    def check_habit(self, user_id, name, date=None):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM habits WHERE name = ? AND active = 1 AND user_id = ?",
            (name, user_id)
        )
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

    def today_checklist(self, user_id, date=None):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.name, COALESCE(hl.completed, 0)
            FROM habits h
            LEFT JOIN habit_logs hl
                ON h.id = hl.habit_id AND hl.date = ?
            WHERE h.active = 1 AND h.user_id = ?
            ORDER BY h.name
        """, (date, user_id))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_habit_streaks(self, user_id, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM habits WHERE name = ? AND user_id = ?",
            (name, user_id)
        )
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

    # ---------- Analytics data (pandas) ----------

    def get_habit_matrix(self, user_id, start_date, end_date):
        import pandas as pd

        conn = get_connection()
        habits_df = pd.read_sql_query(
            "SELECT id, name FROM habits WHERE active = 1 AND user_id = ?", conn, params=(user_id,)
        )
        logs_df = pd.read_sql_query("""
            SELECT hl.habit_id, hl.date, hl.completed
            FROM habit_logs hl
            JOIN habits h ON h.id = hl.habit_id
            WHERE hl.date BETWEEN ? AND ? AND hl.completed = 1 AND h.user_id = ?
        """, conn, params=(start_date, end_date, user_id))
        conn.close()

        date_range = pd.date_range(start=start_date, end=end_date).strftime("%Y-%m-%d")
        matrix = pd.DataFrame(0, index=habits_df["name"], columns=date_range)

        for _, row in logs_df.iterrows():
            habit_name = habits_df.loc[habits_df["id"] == row["habit_id"], "name"]
            if not habit_name.empty:
                matrix.loc[habit_name.values[0], row["date"]] = 1

        return matrix

    def get_mood_trend(self, user_id, start_date, end_date):
        import pandas as pd

        conn = get_connection()
        entries_df = pd.read_sql_query("""
            SELECT created_at, mood
            FROM entries
            WHERE date(created_at) BETWEEN ? AND ? AND mood IS NOT NULL AND user_id = ?
        """, conn, params=(start_date, end_date, user_id))
        conn.close()

        if entries_df.empty:
            return pd.Series(dtype=float)

        entries_df["date"] = pd.to_datetime(entries_df["created_at"]).dt.strftime("%Y-%m-%d")
        entries_df["score"] = entries_df["mood"].map(MOODS)

        daily_avg = entries_df.groupby("date")["score"].mean()
        return daily_avg

    def get_best_worst_days(self, user_id, start_date, end_date):
        from datetime import datetime as dt

        today_str = dt.now().strftime("%Y-%m-%d")
        effective_end = min(end_date, today_str)

        matrix = self.get_habit_matrix(user_id, start_date, effective_end)
        mood_avg = self.get_mood_trend(user_id, start_date, effective_end)

        result = {
            "best_completion_day": None,
            "worst_completion_day": None,
            "best_mood_day": None,
            "worst_mood_day": None,
        }

        if not matrix.empty and len(matrix.index) > 0:
            daily_pct = (matrix.sum(axis=0) / len(matrix.index)) * 100
            if len(daily_pct) > 0:
                result["best_completion_day"] = (daily_pct.idxmax(), daily_pct.max())
                result["worst_completion_day"] = (daily_pct.idxmin(), daily_pct.min())

        if not mood_avg.empty:
            result["best_mood_day"] = (mood_avg.idxmax(), mood_avg.max())
            result["worst_mood_day"] = (mood_avg.idxmin(), mood_avg.min())

        return result

    # ---------- Chart generation (file-based, used by CLI) ----------

    def plot_habit_heatmap(self, user_id, start_date, end_date, save_path="habit_heatmap.png"):
        import matplotlib.pyplot as plt

        matrix = self.get_habit_matrix(user_id, start_date, end_date)

        fig, ax = plt.subplots(figsize=(max(6, len(matrix.columns) * 0.6), max(2, len(matrix.index) * 0.6)))
        ax.imshow(matrix.values, cmap="Greens", vmin=0, vmax=1, aspect="auto")

        ax.set_xticks(range(len(matrix.columns)))
        ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(matrix.index)))
        ax.set_yticklabels(matrix.index)

        ax.set_title(f"Habit Completion: {start_date} to {end_date}")
        fig.tight_layout()
        fig.savefig(save_path, dpi=150)
        plt.close(fig)

        return save_path

    def plot_completion_trend(self, user_id, start_date, end_date, save_path="completion_trend.png"):
        import matplotlib.pyplot as plt

        matrix = self.get_habit_matrix(user_id, start_date, end_date)

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

    def plot_mood_trend(self, user_id, start_date, end_date, save_path="mood_trend.png"):
        import matplotlib.pyplot as plt

        daily_avg = self.get_mood_trend(user_id, start_date, end_date)

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

    def generate_monthly_dashboard(self, user_id, year, month, save_path="monthly_dashboard.png"):
        import matplotlib.pyplot as plt
        import calendar

        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"

        matrix = self.get_habit_matrix(user_id, start_date, end_date)
        mood_avg = self.get_mood_trend(user_id, start_date, end_date)

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
        ax1.imshow(matrix.values, cmap="Greens", vmin=0, vmax=1, aspect="auto")
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

    def export_monthly_report(self, user_id, year, month, save_path=None):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        import calendar

        if save_path is None:
            save_path = f"report_{year}_{month:02d}.pdf"

        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"

        dashboard_path = self.generate_monthly_dashboard(user_id, year, month, save_path="_temp_dashboard.png")
        summary = self.get_best_worst_days(user_id, start_date, end_date)

        with PdfPages(save_path) as pdf:
            img = plt.imread(dashboard_path)
            fig1, ax1 = plt.subplots(figsize=(10, 10))
            ax1.imshow(img)
            ax1.axis("off")
            pdf.savefig(fig1)
            plt.close(fig1)

            fig2, ax2 = plt.subplots(figsize=(8.5, 11))
            ax2.axis("off")

            lines = [f"Monthly Report: {calendar.month_name[month]} {year}", ""]

            if summary["best_completion_day"]:
                day, pct = summary["best_completion_day"]
                lines.append(f"Best completion day:  {day}  ({pct:.0f}%)")
            if summary["worst_completion_day"]:
                day, pct = summary["worst_completion_day"]
                lines.append(f"Worst completion day: {day}  ({pct:.0f}%)")
            if summary["best_mood_day"]:
                day, score = summary["best_mood_day"]
                lines.append(f"Best mood day:        {day}  (score {score:.1f})")
            if summary["worst_mood_day"]:
                day, score = summary["worst_mood_day"]
                lines.append(f"Worst mood day:       {day}  (score {score:.1f})")

            lines.append("")
            lines.append("Habit streaks:")
            for h in self.list_active_habits(user_id):
                current, longest = self.get_habit_streaks(user_id, h.name)
                lines.append(f"  {h.name}: current = {current}, longest = {longest}")

            ax2.text(0.05, 0.95, "\n".join(lines), va="top", fontsize=12, family="monospace")
            pdf.savefig(fig2)
            plt.close(fig2)

        os.remove(dashboard_path)
        return save_path