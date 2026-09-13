# app.py

import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from datetime import datetime

from journal.db import init_db
from journal.manager import JournalManager
from journal.config import MOODS

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-later")

# Security
csrf = CSRFProtect(app)

# Mail Config
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)

# Token Serializer
s = URLSafeTimedSerializer(app.secret_key)

init_db()
jm = JournalManager()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class LoginUser(UserMixin):
    def __init__(self, user):
        self.id = user.id
        self.username = user.username
        self.email = user.email

@login_manager.user_loader
def load_user(user_id):
    user = jm.get_user_by_id(int(user_id))
    if user is None:
        return None
    return LoginUser(user)

@app.route("/")
def home():
    if current_user.is_authenticated:
        checklist_data = jm.get_today_checklist_with_schedule(current_user.id)
        achievements = jm.get_achievements(current_user.id)
        summary = jm.get_dashboard_summary(current_user.id)
        moods = MOODS
        return render_template("home.html", checklist_data=checklist_data, achievements=achievements, summary=summary, moods=moods)
    return render_template("landing.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form.get("email", "").strip()
        password = request.form["password"]

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        try:
            jm.register_user(username, password, email=email if email else None)
        except ValueError as e:
            flash(str(e))
            return redirect(url_for("register"))

        flash("Account created. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        remember = "remember" in request.form

        user = jm.get_user_by_username(username)
        if user is None or not jm.verify_password(user, password):
            flash("Invalid username or password.")
            return redirect(url_for("login"))

        login_user(LoginUser(user), remember=remember)
        flash(f"Welcome back, {user.username}!")
        return redirect(url_for("home"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.")
    return redirect(url_for("login"))

@app.route("/timetable")
@login_required
def timetable():
    grid = jm.get_timetable_grid(current_user.id)
    return render_template("timetable.html", grid=grid)

@app.route("/timetable/block/add", methods=["POST"])
@login_required
def add_timetable_block():
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    if start_time and end_time:
        try:
            jm.add_time_block(current_user.id, start_time, end_time)
            flash("Time block added.")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("timetable"))

@app.route("/timetable/block/delete", methods=["POST"])
@login_required
def delete_timetable_block():
    block_id = request.form.get("block_id")
    if block_id:
        try:
            jm.delete_time_block(current_user.id, int(block_id))
            flash("Time block deleted.")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("timetable"))

@app.route("/timetable/cell", methods=["POST"])
@login_required
def set_timetable_cell():
    data = request.get_json() if request.is_json else request.form
    block_id = data.get("block_id")
    day_of_week = data.get("day_of_week")
    label = data.get("label", "")

    if not block_id or not day_of_week:
        if request.is_json:
            return {"error": "Missing parameters"}, 400
        flash("Missing parameters.")
        return redirect(url_for("timetable"))

    try:
        jm.set_cell(current_user.id, int(block_id), day_of_week, label)
        if request.is_json:
            return {"success": True}
        flash("Cell saved.")
    except ValueError as e:
        if request.is_json:
            return {"error": str(e)}, 400
        flash(str(e))

    return redirect(url_for("timetable"))

@app.route("/habits")
@login_required
def habits():
    active_habits = jm.list_active_habits(current_user.id)
    streaks = {}
    weekly_progress = {}
    schedules = {}
    
    from datetime import datetime, timedelta
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    view_mode = request.args.get("view", "week")
    
    # Week dates calculation
    try:
        week_offset = int(request.args.get("week_offset", 0))
    except ValueError:
        week_offset = 0

    base_monday = (today - timedelta(days=today.weekday())) + timedelta(weeks=week_offset)
    week_dates = [(base_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    week_day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Month view parameters
    try:
        month_num = int(request.args.get("month", today.month))
    except ValueError:
        month_num = today.month

    try:
        month_year = int(request.args.get("month_year", today.year))
    except ValueError:
        month_year = today.year

    # Year view parameters
    year_mode = request.args.get("year_mode", "current")

    week_matrix = jm.get_habit_matrix(current_user.id, week_dates[0], week_dates[-1])
    
    habit_week_status = {}
    today_status = {}
    month_calendars = {}
    year_heatmaps = {}
    
    for h in active_habits:
        schedules[h.id] = jm.get_habit_schedule(h.id)
        if h.frequency_type == 'daily' or h.frequency_type is None:
            streaks[h.name] = jm.get_habit_streaks(current_user.id, h.name)
        else:
            weekly_progress[h.name] = jm.get_weekly_progress(current_user.id, h.id, base_monday.strftime("%Y-%m-%d"))
            
        # Week status per habit
        if not week_matrix.empty and h.name in week_matrix.index:
            habit_week_status[h.name] = [int(week_matrix.loc[h.name, d]) if d in week_matrix.columns else 0 for d in week_dates]
        else:
            habit_week_status[h.name] = [0] * 7
            
        # Today completion status
        if not week_matrix.empty and h.name in week_matrix.index and today_str in week_matrix.columns:
            today_status[h.name] = int(week_matrix.loc[h.name, today_str])
        else:
            today_status[h.name] = 0

        # Month calendar data
        month_calendars[h.name] = jm.get_habit_month_calendar(current_user.id, h.name, month_year, month_num)

        # Year heatmap data
        year_heatmaps[h.name] = jm.get_habit_year_heatmap(current_user.id, h.name, year_mode)

    return render_template(
        "habits.html", 
        habits=active_habits, 
        streaks=streaks, 
        weekly_progress=weekly_progress, 
        schedules=schedules,
        week_dates=week_dates,
        week_day_names=week_day_names,
        today_str=today_str,
        week_offset=week_offset,
        habit_week_status=habit_week_status,
        today_status=today_status,
        view_mode=view_mode,
        month_calendars=month_calendars,
        year_heatmaps=year_heatmaps,
        month_num=month_num,
        month_year=month_year,
        year_mode=year_mode
    )

@app.route("/habits/add", methods=["POST"])
@login_required
def add_habit():
    name = request.form.get("name", "").strip()
    category = request.form.get("category")
    emoji = request.form.get("emoji")
    color = request.form.get("color")
    freq = request.form.get("frequency_type", "daily")
    weekly_target = request.form.get("weekly_target")
    
    days = request.form.getlist("days")
    time = request.form.get("time", "").strip() or None
    
    if not category: category = None
    if not emoji: emoji = None
    if not color: color = None
    
    if weekly_target:
        try:
            weekly_target = int(weekly_target)
        except ValueError:
            weekly_target = None
            
    if name:
        try:
            h = jm.add_habit(current_user.id, name, category, emoji, color, freq, weekly_target)
            if days:
                jm.set_habit_schedule(h.id, days, time)
            flash(f"Habit '{name}' added.")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("habits"))

@app.route("/habits/schedule", methods=["POST"])
@login_required
def edit_schedule():
    habit_id = request.form.get("habit_id")
    days = request.form.getlist("days")
    time = request.form.get("time", "").strip() or None
    redirect_to = request.form.get("redirect_to", "habits")
    
    if habit_id:
        try:
            jm.set_habit_schedule(int(habit_id), days, time)
            flash("Schedule updated successfully.")
        except Exception as e:
            flash(str(e))
    return redirect(url_for(redirect_to))

@app.route("/habits/toggle", methods=["POST"])
@login_required
def toggle_habit():
    data = request.get_json()
    name = data.get("name")
    date = data.get("date")
    
    if not name:
        return {"error": "Missing habit name"}, 400
        
    try:
        new_state = jm.toggle_habit(current_user.id, name, date)
        return {"success": True, "name": name, "completed": new_state}
    except ValueError as e:
        return {"error": str(e)}, 400

@app.route("/habits/remove", methods=["POST"])
@login_required
def remove_habit():
    name = request.form.get("name", "").strip()
    if name:
        try:
            jm.remove_habit(current_user.id, name)
            flash(f"Habit '{name}' removed.")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("habits"))

@app.route("/habits/check", methods=["POST"])
@login_required
def check_habit():
    name = request.form.get("name")
    if name:
        try:
            jm.check_habit(current_user.id, name)
            flash(f"Checked off: {name}")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("home"))

@app.route("/journal", methods=["GET"])
@login_required
def journal():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    mood_filter = request.args.get("mood_filter")
    if mood_filter == "": mood_filter = None
    text_search = request.args.get("text_search")
    
    if not start_date or not end_date:
        today = datetime.now().strftime("%Y-%m-%d")
        from datetime import timedelta
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = today

    entries = jm.search_entries(current_user.id, start_date, end_date, mood_filter, text_search)
    return render_template("journal.html", entries=entries, start_date=start_date, end_date=end_date, moods=MOODS, mood_filter=mood_filter, text_search=text_search)

@app.route("/journal/add", methods=["POST"])
@login_required
def add_entry():
    mood = request.form.get("mood")
    if mood == "":
        mood = None
    note = request.form.get("note", "").strip()
    
    if not mood and not note:
        flash("Cannot add empty entry.")
        return redirect(url_for("home"))
        
    try:
        jm.add_entry(current_user.id, mood, note)
        flash("Journal entry added.")
    except ValueError as e:
        flash(str(e))
        
    return redirect(url_for("home"))

@app.route("/analytics")
@login_required
def analytics():
    today = datetime.now()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    month = int(request.args.get("month", today.month))
    year = int(request.args.get("year", today.year))
    
    if not start_date or not end_date:
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
    summary = jm.get_best_worst_days(current_user.id, start_date, end_date)
    
    return render_template("analytics.html", 
                          start_date=start_date, end_date=end_date, 
                          month=month, year=year, summary=summary)

@app.route("/analytics/heatmap.png")
@login_required
def heatmap_image():
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    buf = jm.plot_habit_heatmap_bytes(current_user.id, start, end)
    return send_file(buf, mimetype="image/png")

@app.route("/analytics/completion.png")
@login_required
def completion_image():
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    buf = jm.plot_completion_trend_bytes(current_user.id, start, end)
    return send_file(buf, mimetype="image/png")

@app.route("/analytics/mood.png")
@login_required
def mood_image():
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    buf = jm.plot_mood_trend_bytes(current_user.id, start, end)
    return send_file(buf, mimetype="image/png")

@app.route("/analytics/export.pdf")
@login_required
def export_pdf():
    year = int(request.args.get("year"))
    month = int(request.args.get("month"))
    buf = jm.export_monthly_report_bytes(current_user.id, year, month)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"report_{year}_{month:02d}.pdf")

@app.route("/stats")
@login_required
def stats():
    range_type = request.args.get("range", "30d")
    if range_type not in ["7d", "30d", "all"]:
        range_type = "30d"
    counts = jm.get_habit_completion_counts(current_user.id, range_type)
    return render_template("stats.html", counts=counts, current_range=range_type)

@app.route("/goals")
@login_required
def goals():
    active_habits = jm.list_active_habits(current_user.id)
    all_goals = jm.list_goals(current_user.id)
    goals_by_habit = {h.id: [] for h in active_habits}
    for g in all_goals:
        if g["habit_id"] in goals_by_habit:
            goals_by_habit[g["habit_id"]].append(g)
    return render_template("goals.html", habits=active_habits, goals_by_habit=goals_by_habit)

@app.route("/goals/add", methods=["POST"])
@login_required
def add_goal():
    habit_id = request.form.get("habit_id")
    description = request.form.get("description", "").strip()
    if habit_id and description:
        try:
            jm.add_goal(current_user.id, int(habit_id), description)
            flash("Goal added successfully.")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("goals"))

@app.route("/goals/toggle", methods=["POST"])
@login_required
def toggle_goal():
    data = request.get_json() if request.is_json else request.form
    goal_id = data.get("goal_id")
    if not goal_id:
        return {"error": "Missing goal_id"}, 400
    try:
        new_state = jm.toggle_goal(current_user.id, int(goal_id))
        if request.is_json:
            return {"success": True, "completed": new_state}
        flash("Goal status updated.")
    except ValueError as e:
        if request.is_json:
            return {"error": str(e)}, 400
        flash(str(e))
    return redirect(url_for("goals"))

@app.route("/goals/edit", methods=["POST"])
@login_required
def edit_goal():
    goal_id = request.form.get("goal_id")
    description = request.form.get("description", "").strip()
    if goal_id and description:
        try:
            jm.edit_goal(current_user.id, int(goal_id), description)
            flash("Goal updated.")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("goals"))

@app.route("/goals/delete", methods=["POST"])
@login_required
def delete_goal():
    goal_id = request.form.get("goal_id")
    if goal_id:
        try:
            jm.delete_goal(current_user.id, int(goal_id))
            flash("Goal deleted.")
        except ValueError as e:
            flash(str(e))
    return redirect(url_for("goals"))

@app.route("/reset-password-request", methods=["GET", "POST"])
def reset_password_request():
    if request.method == "POST":
        email = request.form.get("email").strip()
        user = jm.get_user_by_email(email)
        if user:
            token = s.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            msg = Message('Password Reset Request', sender=app.config.get('MAIL_USERNAME', 'noreply@habitjournal.com'), recipients=[email])
            msg.body = f"Your password reset link is: {reset_url}\nIf you did not request this, please ignore."
            try:
                mail.send(msg)
                flash("A password reset link has been sent to your email.")
            except Exception as e:
                flash(f"Failed to send email. Did you configure SMTP? (Check console for link)")
                print(f"Failed to send email: {e}")
                print(f"Token link: {reset_url}")
        else:
            flash("If that email is registered, a reset link was sent.") # Prevent email enumeration
        return redirect(url_for('login'))
    return render_template("reset_password_request.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadTimeSignature):
        flash('The password reset link is invalid or has expired.')
        return redirect(url_for('reset_password_request'))
        
    if request.method == "POST":
        password = request.form.get("password")
        user = jm.get_user_by_email(email)
        if user:
            jm.update_password(user.id, password)
            flash("Your password has been updated!")
            return redirect(url_for('login'))
    return render_template("reset_password.html")

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true")