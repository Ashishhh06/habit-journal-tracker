# journal/manager.py

import sqlite3
import os
from datetime import datetime
from journal.db import get_connection
from journal.models import Entry, Habit, User
from journal.config import MOODS, PRESET_COLORS
from journal.streaks import compute_streaks


class JournalManager:

    # ---------- User accounts ----------

    def register_user(self, username, password, email=None):
        from werkzeug.security import generate_password_hash

        password_hash = generate_password_hash(password)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email)
            )
            conn.commit()
            new_id = cursor.lastrowid
        except sqlite3.IntegrityError as e:
            conn.close()
            if "email" in str(e).lower():
                raise ValueError(f"Email '{email}' is already registered.")
            raise ValueError(f"Username '{username}' is already taken.")
        conn.close()
        return User(id=new_id, username=username, password_hash=password_hash, email=email)

    def get_user_by_username(self, username):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, email FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return User(id=row[0], username=row[1], password_hash=row[2], email=row[3])

    def get_user_by_id(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, email FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return User(id=row[0], username=row[1], password_hash=row[2], email=row[3])

    def get_user_by_email(self, email):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, email FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return User(id=row[0], username=row[1], password_hash=row[2], email=row[3])

    def update_password(self, user_id, new_password):
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(new_password)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()
        conn.close()

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

    def add_habit(self, user_id, name, category=None, emoji=None, color=None, frequency_type='daily', weekly_target=None):
        conn = get_connection()
        cursor = conn.cursor()
        if not color:
            cursor.execute("SELECT COUNT(*) FROM habits WHERE user_id = ?", (user_id,))
            cnt = cursor.fetchone()[0]
            color = PRESET_COLORS[cnt % len(PRESET_COLORS)]
        try:
            cursor.execute(
                "INSERT INTO habits (user_id, name, active, category, emoji, color, frequency_type, weekly_target) VALUES (?, ?, 1, ?, ?, ?, ?, ?)",
                (user_id, name, category, emoji, color, frequency_type, weekly_target)
            )
            conn.commit()
            new_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Habit '{name}' already exists.")
        conn.close()
        return Habit(id=new_id, user_id=user_id, name=name, active=1, category=category, emoji=emoji, color=color, frequency_type=frequency_type, weekly_target=weekly_target)

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
            "SELECT id, user_id, name, active, category, emoji, color, frequency_type, weekly_target FROM habits WHERE active = 1 AND user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [Habit(id=r[0], user_id=r[1], name=r[2], active=r[3], category=r[4], emoji=r[5], color=r[6], frequency_type=r[7], weekly_target=r[8]) for r in rows]

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
            SELECT h.name, COALESCE(hl.completed, 0), h.category, h.emoji, h.color
            FROM habits h
            LEFT JOIN habit_logs hl
                ON h.id = hl.habit_id AND hl.date = ?
            WHERE h.active = 1 AND h.user_id = ? AND (h.frequency_type IS NULL OR h.frequency_type = 'daily')
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

    def toggle_habit(self, user_id, name, date=None):
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
            "SELECT completed FROM habit_logs WHERE habit_id = ? AND date = ?",
            (habit_id, date)
        )
        log_row = cursor.fetchone()
        
        if log_row is None:
            new_completed = 1
            cursor.execute(
                "INSERT INTO habit_logs (habit_id, date, completed) VALUES (?, ?, ?)",
                (habit_id, date, new_completed)
            )
        else:
            new_completed = 1 - log_row[0]
            cursor.execute(
                "UPDATE habit_logs SET completed = ? WHERE habit_id = ? AND date = ?",
                (new_completed, habit_id, date)
            )
            
        conn.commit()
        conn.close()
        return new_completed

    def get_weekly_progress(self, user_id, habit_id, week_start_date):
        # week_start_date should be Monday 'YYYY-MM-DD'
        start_date_obj = datetime.strptime(week_start_date, "%Y-%m-%d")
        from datetime import timedelta
        end_date_obj = start_date_obj + timedelta(days=6)
        end_date = end_date_obj.strftime("%Y-%m-%d")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT weekly_target FROM habits WHERE id = ? AND user_id = ?",
            (habit_id, user_id)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return 0, 0
            
        target = row[0] or 0
        
        cursor.execute(
            "SELECT COUNT(*) FROM habit_logs WHERE habit_id = ? AND date BETWEEN ? AND ? AND completed = 1",
            (habit_id, week_start_date, end_date)
        )
        completed_count = cursor.fetchone()[0]
        conn.close()
        return completed_count, target

    def search_entries(self, user_id, start_date, end_date, mood_filter=None, text_search=None):
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "SELECT id, user_id, created_at, mood, note FROM entries WHERE date(created_at) BETWEEN ? AND ? AND user_id = ?"
        params = [start_date, end_date, user_id]
        
        if mood_filter:
            query += " AND mood = ?"
            params.append(mood_filter)
            
        if text_search:
            query += " AND note LIKE ?"
            params.append(f"%{text_search}%")
            
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, tuple(params))
        entries = [Entry(id=r[0], user_id=r[1], created_at=r[2], mood=r[3], note=r[4]) for r in cursor.fetchall()]
        conn.close()
        return entries
        
    def get_achievements(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        
        badges = []
        
        cursor.execute("""
            SELECT COUNT(*) FROM habit_logs hl 
            JOIN habits h ON h.id = hl.habit_id 
            WHERE h.user_id = ? AND hl.completed = 1
        """, (user_id,))
        row = cursor.fetchone()
        total_logs = row[0] if row else 0
        
        badges.append({
            "name": "First Steps",
            "earned": total_logs > 0,
            "desc": "First habit check-in ever"
        })
        
        badges.append({
            "name": "Century Club",
            "earned": total_logs >= 100,
            "desc": "100+ total habit check-ins"
        })
        
        cursor.execute("SELECT COUNT(*) FROM entries WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        total_entries = row[0] if row else 0
        badges.append({
            "name": "Reflective",
            "earned": total_entries >= 10,
            "desc": "10+ journal entries logged"
        })
        
        conn.close()
        
        active_habits = self.list_active_habits(user_id)
        max_streak = 0
        for h in active_habits:
            if h.frequency_type == 'daily':
                _, longest = self.get_habit_streaks(user_id, h.name)
                max_streak = max(max_streak, longest)
                
        badges.append({
            "name": "Week Warrior",
            "earned": max_streak >= 7,
            "desc": "7-day streak on any habit"
        })
        
        badges.append({
            "name": "Month Master",
            "earned": max_streak >= 30,
            "desc": "30-day streak on any habit"
        })
        
        from datetime import timedelta
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        matrix = self.get_habit_matrix(user_id, start_date, end_date)
        if not matrix.empty and len(matrix.index) > 0:
            total_possible = len(matrix.columns) * len(matrix.index)
            total_completed = matrix.values.sum()
            rate = (total_completed / total_possible) if total_possible > 0 else 0
            earned_consistent = rate >= 0.80
        else:
            earned_consistent = False
            
        badges.append({
            "name": "Consistent",
            "earned": earned_consistent,
            "desc": "80%+ completion rate over the last 30 days"
        })
        
        return badges
        
    def get_dashboard_summary(self, user_id):
        from datetime import timedelta
        today_str = datetime.now().strftime("%Y-%m-%d")
        start_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        active_habits = self.list_active_habits(user_id)
        active_count = len(active_habits)
        
        best_streak_name = "None"
        best_streak_val = 0
        
        for h in active_habits:
            if h.frequency_type == 'daily' or h.frequency_type is None:
                current, _ = self.get_habit_streaks(user_id, h.name)
                if current > best_streak_val:
                    best_streak_val = current
                    best_streak_name = h.name
                    
        entries, _ = self.view_range(user_id, start_month, today_str)
        journal_count = len(entries)
        
        matrix = self.get_habit_matrix(user_id, today_str, today_str)
        if not matrix.empty and len(matrix.index) > 0:
            daily_pct = float(matrix.values.sum() / len(matrix.index)) * 100
        else:
            daily_pct = 0.0
            
        return {
            "today_pct": daily_pct,
            "best_streak_name": best_streak_name,
            "best_streak_val": best_streak_val,
            "active_count": active_count,
            "journal_count": journal_count
        }

    # ---------- Analytics data (pandas) ----------

    def get_habit_matrix(self, user_id, start_date, end_date):
        import pandas as pd

        conn = get_connection()
        habits_df = pd.read_sql_query(
            "SELECT id, name FROM habits WHERE active = 1 AND user_id = ? AND (frequency_type IS NULL OR frequency_type = 'daily')", conn, params=(user_id,)
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

    # ---------- Chart generation (in-memory, used by Web App) ----------

    def plot_habit_heatmap_bytes(self, user_id, start_date, end_date):
        import matplotlib.pyplot as plt
        import io

        matrix = self.get_habit_matrix(user_id, start_date, end_date)
        fig, ax = plt.subplots(figsize=(max(6, len(matrix.columns) * 0.6), max(2, len(matrix.index) * 0.6)))
        
        if not matrix.empty and len(matrix.index) > 0:
            ax.imshow(matrix.values, cmap="Greens", vmin=0, vmax=1, aspect="auto")
            ax.set_xticks(range(len(matrix.columns)))
            ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
            ax.set_yticks(range(len(matrix.index)))
            ax.set_yticklabels(matrix.index)
        else:
            ax.text(0.5, 0.5, "No habits data", ha="center", va="center")
            ax.set_xticks([])
            ax.set_yticks([])

        ax.set_title(f"Habit Completion: {start_date} to {end_date}")
        fig.tight_layout()
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

    def plot_completion_trend_bytes(self, user_id, start_date, end_date):
        import matplotlib.pyplot as plt
        import io

        matrix = self.get_habit_matrix(user_id, start_date, end_date)

        if matrix.empty or len(matrix.index) == 0:
            daily_pct = [0] * len(matrix.columns)
        else:
            daily_pct = (matrix.sum(axis=0) / len(matrix.index)) * 100

        fig, ax = plt.subplots(figsize=(max(6, len(matrix.columns) * 0.5), 3))
        if not matrix.empty:
            ax.plot(matrix.columns, daily_pct, marker="o", color="#2e7d32", linewidth=2)
            ax.fill_between(matrix.columns, daily_pct, color="#2e7d32", alpha=0.15)
            plt.xticks(rotation=45, ha="right")
        else:
            ax.text(0.5, 0.5, "No habits data", ha="center", va="center")
            ax.set_xticks([])

        ax.set_ylim(0, 105)
        ax.set_ylabel("Completion %")
        ax.set_title(f"Daily Habit Completion: {start_date} to {end_date}")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

    def plot_mood_trend_bytes(self, user_id, start_date, end_date):
        import matplotlib.pyplot as plt
        import io

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
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

    def generate_monthly_dashboard_bytes(self, user_id, year, month):
        import matplotlib.pyplot as plt
        import calendar
        import io

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
        if not matrix.empty and len(matrix.index) > 0:
            ax1.imshow(matrix.values, cmap="Greens", vmin=0, vmax=1, aspect="auto")
            ax1.set_yticks(range(len(matrix.index)))
            ax1.set_yticklabels(matrix.index)
            ax1.set_xticks(range(len(matrix.columns)))
            ax1.set_xticklabels(matrix.columns, rotation=90, fontsize=7)
        ax1.set_title("Habit Completion")

        ax2 = axes[1]
        if not matrix.empty:
            ax2.plot(matrix.columns, daily_pct, marker="o", color="#2e7d32", linewidth=2)
            ax2.fill_between(matrix.columns, daily_pct, color="#2e7d32", alpha=0.15)
            ax2.set_xticks(range(len(matrix.columns)))
            ax2.set_xticklabels([])
        ax2.set_ylim(0, 105)
        ax2.set_ylabel("Completion %")
        ax2.set_title("Daily Completion %")

        ax3 = axes[2]
        if not mood_avg.empty:
            ax3.plot(mood_avg.index, mood_avg.values, marker="o", color="#1565c0", linewidth=2)
        ax3.axhline(0, color="gray", linewidth=0.8, linestyle="--")
        ax3.set_ylim(-2.5, 2.5)
        ax3.set_ylabel("Mood score")
        if not matrix.empty:
            ax3.set_xticks(range(len(matrix.columns)))
            ax3.set_xticklabels(matrix.columns, rotation=90, fontsize=7)
        ax3.set_title("Mood Trend")

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

    def export_monthly_report_bytes(self, user_id, year, month):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        import calendar
        import io

        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"

        summary = self.get_best_worst_days(user_id, start_date, end_date)
        buf = io.BytesIO()

        with PdfPages(buf) as pdf:
            # Generate dashboard directly to a temporary buffer and read it
            # To avoid disk usage, we'll draw the dashboard and save it to the pdf
            dashboard_buf = self.generate_monthly_dashboard_bytes(user_id, year, month)
            img = plt.imread(dashboard_buf, format='png')
            
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

        buf.seek(0)
        return buf

    # ---------- Schedule & Timetable (Phase 4) ----------

    def set_habit_schedule(self, habit_id, days, time=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM habit_schedule WHERE habit_id = ?", (habit_id,))
        for day in days:
            cursor.execute(
                "INSERT INTO habit_schedule (habit_id, day_of_week, time) VALUES (?, ?, ?)",
                (habit_id, day, time if time else None)
            )
        conn.commit()
        conn.close()

    def get_habit_schedule(self, habit_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT day_of_week, time FROM habit_schedule WHERE habit_id = ?", (habit_id,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return {"days": [], "time": None}
        days = [r[0] for r in rows]
        time = rows[0][1] if rows[0][1] else None
        return {"days": days, "time": time}

    def get_weekly_timetable(self, user_id, start_date=None):
        from datetime import datetime, timedelta

        if start_date:
            if isinstance(start_date, str):
                base_dt = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                base_dt = start_date
        else:
            base_dt = datetime.now()

        monday_dt = base_dt - timedelta(days=base_dt.weekday())
        today_str = datetime.now().strftime("%Y-%m-%d")

        conn = get_connection()
        cursor = conn.cursor()

        # Get all active habits for user
        cursor.execute("""
            SELECT id, name, category, emoji, color, frequency_type
            FROM habits
            WHERE user_id = ? AND active = 1
        """, (user_id,))
        habits = cursor.fetchall()

        # Pre-fetch all schedules for active habits
        cursor.execute("""
            SELECT hs.habit_id, hs.day_of_week, hs.time
            FROM habit_schedule hs
            JOIN habits h ON h.id = hs.habit_id
            WHERE h.user_id = ? AND h.active = 1
        """, (user_id,))
        schedules_rows = cursor.fetchall()

        # habit_id -> { "days": set(), "time": str }
        schedules = {}
        for hid, dow, t in schedules_rows:
            if hid not in schedules:
                schedules[hid] = {"days": set(), "time": t}
            schedules[hid]["days"].add(dow)
            if t and not schedules[hid]["time"]:
                schedules[hid]["time"] = t

        # Pre-fetch habit logs for the week
        week_dates = [(monday_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        start_week = week_dates[0]
        end_week = week_dates[-1]

        cursor.execute("""
            SELECT habit_id, date, completed
            FROM habit_logs
            WHERE date BETWEEN ? AND ? AND completed = 1
        """, (start_week, end_week))
        completed_set = set((r[0], r[1]) for r in cursor.fetchall())

        conn.close()

        days_data = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for i, day_name in enumerate(day_names):
            current_date_dt = monday_dt + timedelta(days=i)
            current_date_str = current_date_dt.strftime("%Y-%m-%d")

            day_habits = []
            for h in habits:
                hid, name, cat, emoji, color, freq = h
                sched = schedules.get(hid)

                # Check if habit occurs on this day
                # If no schedule defined, defaults to every day
                occurs = False
                h_time = None
                if not sched or not sched["days"]:
                    occurs = True
                elif day_name in sched["days"]:
                    occurs = True
                    h_time = sched["time"]

                if occurs:
                    is_completed = (hid, current_date_str) in completed_set
                    day_habits.append({
                        "id": hid,
                        "name": name,
                        "category": cat,
                        "emoji": emoji,
                        "color": color,
                        "time": h_time,
                        "completed": is_completed
                    })

            # Sort: timed first (by time), then anytime (by name)
            timed = sorted([h for h in day_habits if h["time"]], key=lambda x: x["time"])
            anytime = sorted([h for h in day_habits if not h["time"]], key=lambda x: x["name"])
            sorted_habits = timed + anytime

            days_data.append({
                "day_name": day_name,
                "date": current_date_str,
                "is_today": (current_date_str == today_str),
                "habits": sorted_habits
            })

        prev_week = (monday_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        next_week = (monday_dt + timedelta(days=7)).strftime("%Y-%m-%d")

        return {
            "start_date": start_week,
            "end_date": end_week,
            "prev_week": prev_week,
            "next_week": next_week,
            "days": days_data
        }

    def get_today_checklist_with_schedule(self, user_id, date_str=None):
        from datetime import datetime
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = target_dt.strftime("%a") # Mon, Tue, etc.

        conn = get_connection()
        cursor = conn.cursor()

        # Get active daily/scheduled habits
        cursor.execute("""
            SELECT id, name, category, emoji, color
            FROM habits
            WHERE user_id = ? AND active = 1 AND (frequency_type IS NULL OR frequency_type = 'daily')
        """, (user_id,))
        habits = cursor.fetchall()

        cursor.execute("""
            SELECT hs.habit_id, hs.day_of_week, hs.time
            FROM habit_schedule hs
            JOIN habits h ON h.id = hs.habit_id
            WHERE h.user_id = ? AND h.active = 1
        """, (user_id,))
        sched_rows = cursor.fetchall()

        schedules = {}
        for hid, dow, t in sched_rows:
            if hid not in schedules:
                schedules[hid] = {"days": set(), "time": t}
            schedules[hid]["days"].add(dow)
            if t and not schedules[hid]["time"]:
                schedules[hid]["time"] = t

        cursor.execute("""
            SELECT habit_id, completed
            FROM habit_logs
            WHERE date = ? AND completed = 1
        """, (date_str,))
        completed_ids = set(r[0] for r in cursor.fetchall())
        conn.close()

        timed_habits = []
        anytime_habits = []

        for hid, name, cat, emoji, color in habits:
            sched = schedules.get(hid)
            occurs = False
            h_time = None
            if not sched or not sched["days"]:
                occurs = True
            elif day_name in sched["days"]:
                occurs = True
                h_time = sched["time"]

            if occurs:
                item = {
                    "id": hid,
                    "name": name,
                    "category": cat,
                    "emoji": emoji,
                    "color": color,
                    "time": h_time,
                    "completed": (hid in completed_ids)
                }
                if h_time:
                    timed_habits.append(item)
                else:
                    anytime_habits.append(item)

        timed_habits.sort(key=lambda x: x["time"])
        anytime_habits.sort(key=lambda x: x["name"])

        return {
            "date": date_str,
            "timed": timed_habits,
            "anytime": anytime_habits
        }

    # ---------- Goals & Stats (Phase 5) ----------

    def add_goal(self, user_id, habit_id_or_name, description):
        if not description or not str(description).strip():
            raise ValueError("Goal description cannot be empty.")
        description = str(description).strip()

        conn = get_connection()
        cursor = conn.cursor()

        # Find habit belonging to user_id
        if isinstance(habit_id_or_name, int) or (isinstance(habit_id_or_name, str) and habit_id_or_name.isdigit()):
            cursor.execute("SELECT id FROM habits WHERE id = ? AND user_id = ? AND active = 1", (int(habit_id_or_name), user_id))
        else:
            cursor.execute("SELECT id FROM habits WHERE name = ? AND user_id = ? AND active = 1", (str(habit_id_or_name), user_id))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Habit not found or access denied.")

        habit_id = row[0]
        created_at = datetime.now().isoformat()

        cursor.execute(
            "INSERT INTO habit_goals (habit_id, description, completed, created_at) VALUES (?, ?, 0, ?)",
            (habit_id, description, created_at)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"id": new_id, "habit_id": habit_id, "description": description, "completed": 0, "created_at": created_at}

    def list_goals(self, user_id, habit_id_or_name=None):
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT g.id, g.habit_id, g.description, g.completed, g.created_at, h.name, h.emoji, h.color
            FROM habit_goals g
            JOIN habits h ON h.id = g.habit_id
            WHERE h.user_id = ? AND h.active = 1
        """
        params = [user_id]

        if habit_id_or_name is not None:
            if isinstance(habit_id_or_name, int) or (isinstance(habit_id_or_name, str) and habit_id_or_name.isdigit()):
                query += " AND h.id = ?"
                params.append(int(habit_id_or_name))
            else:
                query += " AND h.name = ?"
                params.append(str(habit_id_or_name))

        query += " ORDER BY g.completed ASC, g.id ASC"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "habit_id": r[1],
                "description": r[2],
                "completed": r[3],
                "created_at": r[4],
                "habit_name": r[5],
                "habit_emoji": r[6],
                "habit_color": r[7]
            }
            for r in rows
        ]

    def toggle_goal(self, user_id, goal_id):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT g.id, g.completed
            FROM habit_goals g
            JOIN habits h ON h.id = g.habit_id
            WHERE g.id = ? AND h.user_id = ?
        """, (goal_id, user_id))

        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Goal not found or access denied.")

        new_state = 1 if row[1] == 0 else 0
        cursor.execute("UPDATE habit_goals SET completed = ? WHERE id = ?", (new_state, goal_id))
        conn.commit()
        conn.close()
        return new_state

    def edit_goal(self, user_id, goal_id, new_description):
        if not new_description or not str(new_description).strip():
            raise ValueError("Goal description cannot be empty.")
        new_description = str(new_description).strip()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT g.id
            FROM habit_goals g
            JOIN habits h ON h.id = g.habit_id
            WHERE g.id = ? AND h.user_id = ?
        """, (goal_id, user_id))

        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Goal not found or access denied.")

        cursor.execute("UPDATE habit_goals SET description = ? WHERE id = ?", (new_description, goal_id))
        conn.commit()
        conn.close()
        return True

    def delete_goal(self, user_id, goal_id):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT g.id
            FROM habit_goals g
            JOIN habits h ON h.id = g.habit_id
            WHERE g.id = ? AND h.user_id = ?
        """, (goal_id, user_id))

        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Goal not found or access denied.")

        cursor.execute("DELETE FROM habit_goals WHERE id = ?", (goal_id,))
        conn.commit()
        conn.close()
        return True

    def get_habit_completion_counts(self, user_id, range_type='30d'):
        from datetime import datetime, timedelta

        conn = get_connection()
        cursor = conn.cursor()

        today_dt = datetime.now()

        if range_type == '7d':
            start_date = (today_dt - timedelta(days=6)).strftime("%Y-%m-%d")
            query = """
                SELECT h.id, h.name, h.emoji, h.color, COUNT(hl.id) as completion_count
                FROM habits h
                LEFT JOIN habit_logs hl ON hl.habit_id = h.id AND hl.completed = 1 AND hl.date >= ?
                WHERE h.user_id = ? AND h.active = 1
                GROUP BY h.id, h.name, h.emoji, h.color
                ORDER BY completion_count DESC, h.name ASC
            """
            params = [start_date, user_id]
        elif range_type == '30d':
            start_date = (today_dt - timedelta(days=29)).strftime("%Y-%m-%d")
            query = """
                SELECT h.id, h.name, h.emoji, h.color, COUNT(hl.id) as completion_count
                FROM habits h
                LEFT JOIN habit_logs hl ON hl.habit_id = h.id AND hl.completed = 1 AND hl.date >= ?
                WHERE h.user_id = ? AND h.active = 1
                GROUP BY h.id, h.name, h.emoji, h.color
                ORDER BY completion_count DESC, h.name ASC
            """
            params = [start_date, user_id]
        else:  # 'all'
            query = """
                SELECT h.id, h.name, h.emoji, h.color, COUNT(hl.id) as completion_count
                FROM habits h
                LEFT JOIN habit_logs hl ON hl.habit_id = h.id AND hl.completed = 1
                WHERE h.user_id = ? AND h.active = 1
                GROUP BY h.id, h.name, h.emoji, h.color
                ORDER BY completion_count DESC, h.name ASC
            """
            params = [user_id]

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "name": r[1],
                "emoji": r[2] or "⭐",
                "color": r[3] or "#4caf50",
                "count": r[4]
            }
            for r in rows
        ]

    # ---------- Timetable Grid (PRD Redesign) ----------

    def add_time_block(self, user_id, start_time, end_time):
        if not start_time or not end_time:
            raise ValueError("Start time and end time are required.")
        
        start_time = start_time.strip()
        end_time = end_time.strip()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO timetable_blocks (user_id, start_time, end_time) VALUES (?, ?, ?)",
            (user_id, start_time, end_time)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return {"id": new_id, "user_id": user_id, "start_time": start_time, "end_time": end_time}

    def delete_time_block(self, user_id, block_id):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM timetable_blocks WHERE id = ? AND user_id = ?", (block_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Time block not found or access denied.")

        # Explicitly delete cells first to respect foreign keys
        cursor.execute("DELETE FROM timetable_cells WHERE block_id = ?", (block_id,))
        cursor.execute("DELETE FROM timetable_blocks WHERE id = ?", (block_id,))
        conn.commit()
        conn.close()
        return True

    def set_cell(self, user_id, block_id, day_of_week, label):
        days_valid = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if day_of_week not in days_valid:
            raise ValueError(f"Invalid day of week: {day_of_week}")

        conn = get_connection()
        cursor = conn.cursor()

        # Verify ownership
        cursor.execute("SELECT id FROM timetable_blocks WHERE id = ? AND user_id = ?", (block_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError("Time block not found or access denied.")

        clean_label = str(label).strip() if label else ""

        if clean_label == "":
            cursor.execute("DELETE FROM timetable_cells WHERE block_id = ? AND day_of_week = ?", (block_id, day_of_week))
        else:
            cursor.execute(
                "INSERT OR REPLACE INTO timetable_cells (block_id, day_of_week, label) VALUES (?, ?, ?)",
                (block_id, day_of_week, clean_label)
            )

        conn.commit()
        conn.close()
        return True

    def get_timetable_grid(self, user_id):
        from datetime import datetime

        def _fmt_time(t_str):
            try:
                dt = datetime.strptime(t_str, "%H:%M")
                return dt.strftime("%I:%M %p").lstrip("0")
            except Exception:
                return t_str

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, start_time, end_time FROM timetable_blocks WHERE user_id = ? ORDER BY start_time ASC, end_time ASC",
            (user_id,)
        )
        blocks = cursor.fetchall()

        cursor.execute("""
            SELECT c.block_id, c.day_of_week, c.label
            FROM timetable_cells c
            JOIN timetable_blocks b ON b.id = c.block_id
            WHERE b.user_id = ?
        """, (user_id,))
        cells_rows = cursor.fetchall()
        conn.close()

        # Group cells by block_id
        cells_by_block = {}
        for b_id, dow, lbl in cells_rows:
            if b_id not in cells_by_block:
                cells_by_block[b_id] = {}
            cells_by_block[b_id][dow] = lbl

        days_list = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        grid = []

        for b_id, s_time, e_time in blocks:
            b_cells = cells_by_block.get(b_id, {})
            row_cells = {d: b_cells.get(d, "") for d in days_list}
            formatted_range = f"{_fmt_time(s_time)}–{_fmt_time(e_time)}"
            grid.append({
                "id": b_id,
                "start_time": s_time,
                "end_time": e_time,
                "formatted_time": formatted_range,
                "cells": row_cells
            })

        return grid

    # ---------- Month Calendar & Year Heatmap (PRD Overhaul) ----------

    def get_habit_month_calendar(self, user_id, habit_name, year, month):
        import calendar

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, color, emoji FROM habits WHERE name = ? AND user_id = ? AND active = 1", (habit_name, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Habit '{habit_name}' not found or access denied.")

        habit_id, color, emoji = row[0], row[1], row[2]

        start_date = f"{year:04d}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year:04d}-{month:02d}-{last_day:02d}"

        cursor.execute("""
            SELECT date FROM habit_logs
            WHERE habit_id = ? AND date BETWEEN ? AND ? AND completed = 1
        """, (habit_id, start_date, end_date))
        completed_dates = set(r[0] for r in cursor.fetchall())
        conn.close()

        # Sunday first: firstweekday=6
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)

        weeks_grid = []
        for week in month_days:
            week_slots = []
            for d in week:
                if d == 0:
                    week_slots.append(None)
                else:
                    d_str = f"{year:04d}-{month:02d}-{d:02d}"
                    week_slots.append({
                        "date": d_str,
                        "day": d,
                        "completed": (d_str in completed_dates)
                    })
            weeks_grid.append(week_slots)

        prev_m = month - 1 if month > 1 else 12
        prev_y = year if month > 1 else year - 1
        next_m = month + 1 if month < 12 else 1
        next_y = year if month < 12 else year + 1

        return {
            "habit_name": habit_name,
            "color": color or "#4caf50",
            "emoji": emoji or "⭐",
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "prev_year": prev_y,
            "prev_month": prev_m,
            "next_year": next_y,
            "next_month": next_m,
            "weeks": weeks_grid,
            "total_checkins": len(completed_dates),
            "weekday_headers": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        }

    def get_habit_year_heatmap(self, user_id, habit_name, mode="current"):
        from datetime import datetime, date, timedelta
        import calendar

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, color, emoji FROM habits WHERE name = ? AND user_id = ? AND active = 1", (habit_name, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Habit '{habit_name}' not found or access denied.")

        habit_id, color, emoji = row[0], row[1], row[2]

        today = datetime.now().date()

        # Parse mode
        if str(mode).lower() == "current":
            target_end_dt = today
            target_start_dt = today - timedelta(days=364)
            label = "in the past year"
        else:
            try:
                yr = int(mode)
                target_start_dt = date(yr, 1, 1)
                target_end_dt = date(yr, 12, 31)
                label = f"in {yr}"
            except ValueError:
                target_end_dt = today
                target_start_dt = today - timedelta(days=364)
                label = "in the past year"

        # Align start_dt to preceding Sunday so columns align to Sunday-start
        # Python weekday(): 0=Mon, 1=Tue, ..., 6=Sun
        sun_offset = (target_start_dt.weekday() + 1) % 7
        start_dt = target_start_dt - timedelta(days=sun_offset)

        # Align end_dt to Saturday of the last week column
        sat_offset = (5 - target_end_dt.weekday()) % 7
        end_dt = target_end_dt + timedelta(days=sat_offset)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        cursor.execute("""
            SELECT date FROM habit_logs
            WHERE habit_id = ? AND date BETWEEN ? AND ? AND completed = 1
        """, (habit_id, start_str, end_str))
        completed_dates = set(r[0] for r in cursor.fetchall())

        # Available years query
        cursor.execute("""
            SELECT DISTINCT strftime('%Y', date) FROM habit_logs
            WHERE habit_id = ? AND completed = 1
        """, (habit_id,))
        year_rows = cursor.fetchall()
        available_years = sorted(set([today.year] + [int(r[0]) for r in year_rows if r[0] and r[0].isdigit()]), reverse=True)

        conn.close()

        # Calculate max streak within target range
        range_completed = [d for d in completed_dates if target_start_dt.strftime("%Y-%m-%d") <= d <= target_end_dt.strftime("%Y-%m-%d")]
        _, max_streak = compute_streaks(range_completed)

        # Build week columns
        weeks = []
        seen_months = set()
        curr_dt = start_dt

        while curr_dt <= end_dt:
            week_days = []
            month_label_for_week = None

            for d_idx in range(7):
                d_str = curr_dt.strftime("%Y-%m-%d")
                in_target_range = (target_start_dt <= curr_dt <= target_end_dt)
                is_done = (d_str in completed_dates) if in_target_range else False

                # Month label check: first day of month encountered in target range
                if in_target_range and curr_dt.month not in seen_months:
                    month_label_for_week = calendar.month_abbr[curr_dt.month]
                    seen_months.add(curr_dt.month)

                week_days.append({
                    "date": d_str,
                    "day_num": curr_dt.day,
                    "completed": is_done,
                    "in_range": in_target_range
                })
                curr_dt += timedelta(days=1)

            weeks.append({
                "month_label": month_label_for_week,
                "days": week_days
            })

        total_checkins = len(range_completed)

        return {
            "habit_name": habit_name,
            "color": color or "#4caf50",
            "emoji": emoji or "⭐",
            "mode": mode,
            "label": label,
            "total_checkins": total_checkins,
            "total_active_days": total_checkins,
            "max_streak": max_streak,
            "weeks": weeks,
            "available_years": available_years,
            "weekday_labels": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        }