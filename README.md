# Habit Journal Tracker

A CLI and Web application for tracking habits and journaling daily entries.
This project features a secure Flask web interface with multi-user authentication, in-memory chart generation, email-based password resets, and a modern UI.

## Web App Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   For production or full functionality, configure the following environment variables (e.g. in a `.env` file or export them directly):
   - `FLASK_SECRET_KEY`: A random string for session signing.
   - `MAIL_SERVER`: SMTP server for password reset emails (default `smtp.gmail.com`).
   - `MAIL_PORT`: SMTP port (default `587`).
   - `MAIL_USERNAME`: Your SMTP username/email.
   - `MAIL_PASSWORD`: Your SMTP app password.

3. **Run the App:**
   ```bash
   python app.py
   ```
   The app will run at `http://127.0.0.1:5000/`.

## Screenshots

<!-- Add a screenshot of the finished web app here -->
![Web App Dashboard](screenshot_placeholder.png)

## CLI Usage

The CLI remains fully functional and operates on a local user account.
```bash
python cli.py today
python cli.py view --start 2026-08-01 --end 2026-08-31
```
