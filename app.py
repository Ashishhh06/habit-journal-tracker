# app.py

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from journal.db import init_db
from journal.manager import JournalManager

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-later"

init_db()
jm = JournalManager()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class LoginUser(UserMixin):
    """Wraps our journal.models.User so Flask-Login can work with it."""
    def __init__(self, user):
        self.id = user.id
        self.username = user.username


@login_manager.user_loader
def load_user(user_id):
    user = jm.get_user_by_id(int(user_id))
    if user is None:
        return None
    return LoginUser(user)


@app.route("/")
def home():
    return render_template("base.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        try:
            jm.register_user(username, password)
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


if __name__ == "__main__":
    app.run(debug=True)