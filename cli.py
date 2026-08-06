# cli.py

import click
from journal.db import init_db
from journal.manager import JournalManager
from datetime import datetime

jm = JournalManager()


@click.group()
def cli():
    """A CLI journal and habit tracker."""
    init_db()  # ensures tables exist every time the CLI runs


@cli.command()
@click.option("--mood", default=None, help="Your mood (e.g. happy, sad, neutral)")
@click.option("--note", default="", help="A short note for this entry")
def add(mood, note):
    """Add a new journal entry."""
    try:
        entry = jm.add_entry(mood=mood, note=note)
        click.echo(f"Entry added: {entry}")
    except ValueError as e:
        click.echo(f"Error: {e}")



@cli.command()
def today():
    """Show today's habit checklist."""
    checklist = jm.today_checklist()
    if not checklist:
        click.echo("No active habits yet. Add one with: habit add <name>")
        return
    click.echo(f"Today ({datetime.now().strftime('%Y-%m-%d')})")
    for name, completed in checklist:
        mark = "x" if completed else " "
        click.echo(f"[{mark}] {name}")


@cli.command()
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
def view(start, end):
    """View entries and habit completions in a date range."""
    entries, habit_completions = jm.view_range(start, end)

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
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
def heatmap(start, end):
    """Generate a habit completion heatmap image."""
    path = jm.plot_habit_heatmap(start, end)
    click.echo(f"Heatmap saved to {path}")




@cli.group()
def habit():
    """Manage habits."""
    pass


@habit.command("add")
@click.argument("name")
def habit_add(name):
    """Add a new habit."""
    try:
        h = jm.add_habit(name)
        click.echo(f"Habit added: {h}")
    except ValueError as e:
        click.echo(f"Error: {e}")


@habit.command("remove")
@click.argument("name")
def habit_remove(name):
    """Remove (deactivate) a habit."""
    try:
        jm.remove_habit(name)
        click.echo(f"Habit '{name}' removed.")
    except ValueError as e:
        click.echo(f"Error: {e}")


@habit.command("list")
def habit_list():
    """List all active habits."""
    habits = jm.list_active_habits()
    if not habits:
        click.echo("No active habits yet.")
    for h in habits:
        click.echo(f"- {h.name}")


@habit.command("check")
@click.argument("name")
def habit_check(name):
    """Mark a habit as done for today."""
    try:
        jm.check_habit(name)
        click.echo(f"Checked '{name}' for today.")
    except ValueError as e:
        click.echo(f"Error: {e}")

@habit.command("streak")
@click.argument("name")
def habit_streak(name):
    """Show current and longest streak for a habit."""
    try:
        current, longest = jm.get_habit_streaks(name)
        click.echo(f"{name}: current streak = {current}, longest streak = {longest}")
    except ValueError as e:
        click.echo(f"Error: {e}")


if __name__ == "__main__":
    cli()