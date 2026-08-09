# cli.py

import click
from datetime import datetime
from journal.db import init_db
from journal.manager import JournalManager

jm = JournalManager()

DEFAULT_USERNAME = "local"
DEFAULT_PASSWORD = "local-cli-user"  # not security-sensitive; CLI is single-user/local only


def get_local_user():
    user = jm.get_user_by_username(DEFAULT_USERNAME)
    if user is None:
        user = jm.register_user(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    return user


@click.group()
@click.pass_context
def cli(ctx):
    """A CLI journal and habit tracker."""
    init_db()
    ctx.obj = get_local_user()


@cli.command()
@click.pass_context
@click.option("--mood", default=None, help="Your mood (e.g. happy, sad, neutral)")
@click.option("--note", default="", help="A short note for this entry")
def add(ctx, mood, note):
    """Add a new journal entry."""
    try:
        entry = jm.add_entry(user_id=ctx.obj.id, mood=mood, note=note)
        click.echo(f"Entry added: {entry}")
    except ValueError as e:
        click.echo(f"Error: {e}")


@cli.group()
def habit():
    """Manage habits."""
    pass


@habit.command("add")
@click.pass_context
@click.argument("name")
def habit_add(ctx, name):
    """Add a new habit."""
    try:
        h = jm.add_habit(ctx.obj.id, name)
        click.echo(f"Habit added: {h}")
    except ValueError as e:
        click.echo(f"Error: {e}")


@habit.command("remove")
@click.pass_context
@click.argument("name")
def habit_remove(ctx, name):
    """Remove (deactivate) a habit."""
    try:
        jm.remove_habit(ctx.obj.id, name)
        click.echo(f"Habit '{name}' removed.")
    except ValueError as e:
        click.echo(f"Error: {e}")


@habit.command("list")
@click.pass_context
def habit_list(ctx):
    """List all active habits."""
    habits = jm.list_active_habits(ctx.obj.id)
    if not habits:
        click.echo("No active habits yet.")
    for h in habits:
        click.echo(f"- {h.name}")


@habit.command("check")
@click.pass_context
@click.argument("name")
def habit_check(ctx, name):
    """Mark a habit as done for today."""
    try:
        jm.check_habit(ctx.obj.id, name)
        click.echo(f"Checked '{name}' for today.")
    except ValueError as e:
        click.echo(f"Error: {e}")


@habit.command("streak")
@click.pass_context
@click.argument("name")
def habit_streak(ctx, name):
    """Show current and longest streak for a habit."""
    try:
        current, longest = jm.get_habit_streaks(ctx.obj.id, name)
        click.echo(f"{name}: current streak = {current}, longest streak = {longest}")
    except ValueError as e:
        click.echo(f"Error: {e}")


@cli.command()
@click.pass_context
def today(ctx):
    """Show today's habit checklist."""
    checklist = jm.today_checklist(ctx.obj.id)
    if not checklist:
        click.echo("No active habits yet. Add one with: habit add <name>")
        return
    click.echo(f"Today ({datetime.now().strftime('%Y-%m-%d')})")
    for name, completed in checklist:
        mark = "x" if completed else " "
        click.echo(f"[{mark}] {name}")


@cli.command()
@click.pass_context
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
def view(ctx, start, end):
    """View entries and habit completions in a date range."""
    entries, habit_completions = jm.view_range(ctx.obj.id, start, end)

    click.echo(f"Entries from {start} to {end}:")
    if not entries:
        click.echo("  (none)")
    for e in entries:
        click.echo(f"  [{e.created_at}] mood={e.mood} - {e.note}")

    click.echo(f"\nHabit completions from {start} to {end}:")
    if not habit_completions:
        click.echo("  (none)")
    for name, date in habit_completions:
        click.echo(f"  {date} - {name}")


@cli.command()
@click.pass_context
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
def heatmap(ctx, start, end):
    """Generate a habit completion heatmap image."""
    path = jm.plot_habit_heatmap(ctx.obj.id, start, end)
    click.echo(f"Heatmap saved to {path}")


@cli.command()
@click.pass_context
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
def trend(ctx, start, end):
    """Generate a daily completion percentage trend chart."""
    path = jm.plot_completion_trend(ctx.obj.id, start, end)
    click.echo(f"Trend chart saved to {path}")


@cli.command()
@click.pass_context
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
def mood(ctx, start, end):
    """Generate a mood trend chart."""
    path = jm.plot_mood_trend(ctx.obj.id, start, end)
    click.echo(f"Mood chart saved to {path}")


@cli.command()
@click.pass_context
@click.option("--year", required=True, type=int, help="Year, e.g. 2026")
@click.option("--month", required=True, type=int, help="Month, 1-12")
def dashboard(ctx, year, month):
    """Generate a full monthly analytics dashboard."""
    path = jm.generate_monthly_dashboard(ctx.obj.id, year, month)
    click.echo(f"Dashboard saved to {path}")


@cli.command()
@click.pass_context
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
def summary(ctx, start, end):
    """Show best/worst days for completion and mood."""
    result = jm.get_best_worst_days(ctx.obj.id, start, end)

    click.echo(f"Summary: {start} to {end}")

    if result["best_completion_day"]:
        day, pct = result["best_completion_day"]
        click.echo(f"  Best completion day:  {day} ({pct:.0f}%)")
    if result["worst_completion_day"]:
        day, pct = result["worst_completion_day"]
        click.echo(f"  Worst completion day: {day} ({pct:.0f}%)")
    if result["best_mood_day"]:
        day, score = result["best_mood_day"]
        click.echo(f"  Best mood day:        {day} (score {score:.1f})")
    if result["worst_mood_day"]:
        day, score = result["worst_mood_day"]
        click.echo(f"  Worst mood day:       {day} (score {score:.1f})")

    if not any(result.values()):
        click.echo("  Not enough data yet.")


@cli.command()
@click.pass_context
@click.option("--year", required=True, type=int, help="Year, e.g. 2026")
@click.option("--month", required=True, type=int, help="Month, 1-12")
def export(ctx, year, month):
    """Export a full monthly report as a PDF."""
    path = jm.export_monthly_report(ctx.obj.id, year, month)
    click.echo(f"Report exported to {path}")


if __name__ == "__main__":
    cli()