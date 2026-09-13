# HabitJournal

A full-stack habit-tracking and journaling platform — built as both a Python CLI tool and a multi-user Flask web application — that turns daily habit check-ins and mood entries into streaks, trends, and visual analytics.

## Overview

HabitJournal lets users track daily/weekly habits, log journal entries with mood, and see their consistency reflected back through streaks, completion percentages, mood trends, and a downloadable monthly report. It started as a command-line tool and was extended into a full multi-user web app with authentication, a dashboard, an achievements system, a personal weekly timetable, and PDF exports — all sharing the same underlying data and business-logic layer.

## Problem Statement

Most people who try to build habits lose track of their own consistency — they don't know if they're actually improving, which habits they're neglecting, or how their mood correlates with their routines. Simple checklist apps show *whether* you did something today, but rarely help you see the *pattern* over weeks and months. HabitJournal addresses this by pairing daily tracking with analytics: streaks, completion-rate trends, mood correlation, and a clear best/worst-day summary, so the data a user generates by just checking things off actually becomes useful feedback.

## Dataset

The "dataset" here is user-generated, not external — each user's own habit check-ins and journal entries, stored in a normalized SQLite schema:

- **users** — accounts (hashed passwords, optional email for password reset)
- **entries** — journal entries (timestamp, mood, note); multiple per day supported
- **habits** — user-defined habits (name, category, emoji, color, active/removed status, daily or weekly-target frequency)
- **habit_logs** — one row per habit per day marking completion (the core time-series data behind every chart)
- **habit_schedule**, **habit_goals**, **timetable_blocks/cells** — supporting tables for scheduling, sub-goals, and the personal weekly timetable

All queries are scoped per user, so each account's data is fully isolated.

## Tools and Technologies

Python · Flask · Flask-Login · Flask-WTF · Flask-Mail · SQLite · Click (CLI) · Pandas · Matplotlib · Pytest · Jinja2 · vanilla HTML/CSS/JS

## Methods

- **Streak computation** — a pure-function algorithm that walks a habit's completion dates to compute current and longest streaks, correctly handling gaps and same-day/yesterday edge cases (covered by dedicated unit tests).
- **Mood scoring** — a configurable mood vocabulary (e.g. happy/neutral/sad) mapped to numeric scores, averaged per day with Pandas when multiple entries exist on the same day.
- **Completion-rate aggregation** — habit check-ins reshaped into a habit × date matrix with Pandas, used to compute daily completion percentages and power the heatmap visualization.
- **Best/worst-day analysis** — Pandas `idxmax`/`idxmin` over the completion and mood series to surface standout days within any date range.
- **Chart generation** — Matplotlib for the habit heatmap, completion trend, mood trend, combined monthly dashboard, and multi-page PDF export.

## Key Insights

The analytics layer is designed to answer the questions a plain checklist can't:
- *Am I actually consistent, or just checking boxes occasionally?* → completion % trend
- *Which habits am I neglecting?* → per-habit heatmap and streaks
- *Does my mood track with my habits?* → mood trend alongside completion trend
- *What was my best/worst day this month, and why?* → best/worst-day summary

## Dashboard / Model / Output

- **Dashboard** — summary stat cards (today's completion %, best streak, active habits, journal entry count), an achievements row, and an interactive checklist
- **Habits page** — habit cards with streaks, category, and color coding
- **Stats page** — bar chart comparing habit completions across 7-day/30-day/all-time ranges
- **Weekly Timetable** — a free-form personal schedule grid
- **Goals page** — long-term objectives tied to individual habits
- **Analytics page** — heatmap, completion trend, mood trend, and one-click PDF report export



## How to Run This Project

```bash
git clone https://github.com/Ashishhh06/habit-journal-tracker.git
cd habit-journal-tracker
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to a new file called `.env`, and fill in your own values.

Then run:
```bash
python app.py
```
Open `http://127.0.0.1:5000` in your browser.
```

## Results and Conclusions

The project demonstrates a complete data lifecycle: user input → normalized relational storage → Pandas-based aggregation → Matplotlib visualization → exportable reports, wrapped in two working interfaces (CLI and multi-user web app) that share one tested business-logic layer. It shows that consistent daily data, even something as simple as a checked box, becomes genuinely informative once aggregated and visualized correctly.

## Future Work

- Push notifications/reminders for scheduled habits
- Habit correlation analysis (which habits tend to succeed or fail together)
- Data export (CSV/JSON) for users who want their raw data
- Mobile-optimized/PWA version
- Social/shared accountability features (optional, opt-in)

## Author and Contact

Ashish Kaviti - [GitHub](https://github.com/Ashishhh06)
              - [Linkedin](https://www.linkedin.com/in/ashish-kaviti-8a39b1309/)
              - [Email](kavitiashish6187@gmail.com)
