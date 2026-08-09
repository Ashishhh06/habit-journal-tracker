# app.py

from flask import Flask
from journal.db import init_db

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-later"  # needed for sessions; we'll handle this properly soon

init_db()


@app.route("/")
def home():
    return "Habit Journal Tracker is running!"


if __name__ == "__main__":
    app.run(debug=True)