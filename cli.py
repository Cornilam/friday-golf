"""CLI commands for Friday Golf admin tasks."""

import sqlite3
from datetime import date, datetime

import click

import db
import scraper
import scheduler as sched


@click.group()
def cli() -> None:
    """Friday Golf — automated weekly golf coordination."""
    db.init_db()


@cli.command()
@click.argument("name")
@click.argument("email")
def add_member(name: str, email: str) -> None:
    """Add a new member to the golf group."""
    try:
        member = db.add_member(name, email)
        click.echo(f"Added {member.name} ({member.email})")
    except sqlite3.IntegrityError:
        click.echo(f"Error: {email} is already a member.", err=True)


@cli.command()
@click.argument("email")
def remove_member(email: str) -> None:
    """Deactivate a member by email."""
    if db.deactivate_member(email):
        click.echo(f"Deactivated {email}")
    else:
        click.echo(f"No active member found with email {email}", err=True)


@cli.command()
def list_members() -> None:
    """Show all active members."""
    members = db.get_active_members()
    if not members:
        click.echo("No active members.")
        return
    for m in members:
        click.echo(f"  {m.name} <{m.email}>")
    click.echo(f"\n{len(members)} active member(s)")


@cli.command()
@click.argument("course")
@click.argument("time")  # e.g. "2025-03-14 08:00"
@click.option("--spots", default=4, help="Number of spots")
@click.option("--holes", default=18, help="9 or 18 holes")
@click.option("--price", default="", help="Price display text (e.g. '$35')")
def add_tee_time(course: str, time: str, spots: int, holes: int, price: str) -> None:
    """Manually add a tee time for the current week. TIME format: 'YYYY-MM-DD HH:MM'."""
    week = db.get_current_week()
    if not week:
        click.echo("No open week. Send invites first or create a week.", err=True)
        return

    try:
        tee_dt = datetime.strptime(time, "%Y-%m-%d %H:%M")
    except ValueError:
        click.echo("Invalid time format. Use 'YYYY-MM-DD HH:MM'.", err=True)
        return

    tt = db.add_tee_time(week.id, course, tee_dt, holes=holes, price_display=price, spots=spots)
    click.echo(f"Added tee time: {tt.course_name} at {tt.tee_time} ({tt.spots} spots)")


@cli.command()
@click.option("--date", "target_date", default=None, help="Date to scrape (YYYY-MM-DD). Defaults to next Friday.")
def scrape_times(target_date: str | None) -> None:
    """Scrape tee times from Milwaukee County WebTrac."""
    if target_date:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            click.echo("Invalid date format. Use YYYY-MM-DD.", err=True)
            return
    else:
        d = None

    click.echo("Scraping tee times from WebTrac...")
    try:
        saved = scraper.scrape_and_save(target_date=d)
        click.echo(f"Done. Saved {saved} tee times.")
    except Exception as e:
        click.echo(f"Scrape failed: {e}", err=True)


@cli.command()
def list_times() -> None:
    """Show scraped tee times for the current week."""
    week = db.get_current_week()
    if not week:
        click.echo("No open week.")
        return

    tee_times = db.get_tee_times(week.id)
    if not tee_times:
        click.echo("No tee times found for this week.")
        return

    friday = date.fromisoformat(week.week_of)
    click.echo(f"Tee times for Friday {friday.strftime('%b %d')}:\n")
    for tt in tee_times:
        source = "scraped" if tt.scraped_at else "manual"
        price = f" {tt.price_display}" if tt.price_display else ""
        click.echo(f"  {tt.course_name} — {tt.tee_time}{price} ({tt.spots} spots) [{source}]")


@cli.command()
def trigger_invite() -> None:
    """Manually send this week's invite emails."""
    sched.job_send_invites()
    click.echo("Invites sent.")


@cli.command()
def trigger_reminders() -> None:
    """Manually send reminder emails to non-respondents."""
    sched.job_send_reminders()
    click.echo("Reminders sent.")


@cli.command()
def trigger_pairings() -> None:
    """Manually close registration and send pairings."""
    sched.job_close_and_pair()
    click.echo("Pairings generated and sent.")


@cli.command()
def check_replies() -> None:
    """Manually check inbox for new replies."""
    sched.job_check_replies()
    click.echo("Replies checked.")


@cli.command()
def status() -> None:
    """Show current week's registration status."""
    week = db.get_current_week()
    if not week:
        click.echo("No open week.")
        return

    friday = date.fromisoformat(week.week_of)
    click.echo(f"Week of Friday {friday.strftime('%b %d')} — Status: {week.status}\n")

    regs = db.get_registrations(week.id)
    ins = [r for r in regs if r.status == "in"]
    outs = [r for r in regs if r.status == "out"]
    non_resp = db.get_non_respondents(week.id)

    if ins:
        click.echo("IN:")
        conn = db.get_connection()
        for r in ins:
            row = conn.execute("SELECT name FROM members WHERE id = ?", (r.member_id,)).fetchone()
            click.echo(f"  {row['name']}")
        conn.close()

    if outs:
        click.echo("\nOUT:")
        conn = db.get_connection()
        for r in outs:
            row = conn.execute("SELECT name FROM members WHERE id = ?", (r.member_id,)).fetchone()
            click.echo(f"  {row['name']}")
        conn.close()

    if non_resp:
        click.echo("\nNO RESPONSE:")
        for m in non_resp:
            click.echo(f"  {m.name}")

    click.echo(f"\nTotal: {len(ins)} in, {len(outs)} out, {len(non_resp)} no response")

    # Show tee times
    tee_times = db.get_tee_times(week.id)
    if tee_times:
        click.echo("\nTee Times:")
        for tt in tee_times:
            source = "scraped" if tt.scraped_at else "manual"
            price = f" {tt.price_display}" if tt.price_display else ""
            click.echo(f"  {tt.course_name} — {tt.tee_time}{price} ({tt.spots} spots) [{source}]")

    # Show pairings if they exist
    pairings = db.get_pairings(week.id)
    if pairings:
        click.echo("\nPairings:")
        for g in pairings:
            names = ", ".join(p["name"] for p in g["players"])
            tee = g.get("tee_time", "TBD")
            click.echo(f"  Group {g['group_number']} ({tee}): {names}")


@cli.command()
@click.argument("course")
@click.argument("date_str")  # e.g. "2026-03-13"
@click.argument("time_str")  # e.g. "8:00 am"
@click.option("--players", default=4, help="Number of players")
@click.option("--holes", default=18, help="9 or 18 holes")
def book_time(course: str, date_str: str, time_str: str, players: int, holes: int) -> None:
    """Book a tee time on WebTrac. Opens browser for checkout.

    COURSE: course name (e.g. 'Greenfield' or 'Brown Deer')
    DATE_STR: date in YYYY-MM-DD format
    TIME_STR: time to book (e.g. '8:00 am')
    """
    import config as cfg

    # Look up course code
    course_code = None
    for name, code in cfg.COURSES.items():
        if name.lower() == course.lower():
            course_code = code
            break
    if not course_code:
        click.echo(f"Unknown course '{course}'. Available: {', '.join(cfg.COURSES.keys())}", err=True)
        return

    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        click.echo("Invalid date format. Use YYYY-MM-DD.", err=True)
        return

    click.echo(f"Booking {course} at {time_str} on {d.strftime('%b %d')}...")
    try:
        success = scraper.book_tee_time(course_code, d, time_str, players, holes)
        if success:
            click.echo("Booking complete!")
        else:
            click.echo("Booking failed. Check logs for details.", err=True)
    except Exception as e:
        click.echo(f"Booking error: {e}", err=True)


if __name__ == "__main__":
    cli()
