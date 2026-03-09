"""APScheduler jobs for the Friday Golf workflow."""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

import config
import db
import email_client
import pairing_engine
import scraper

logger = logging.getLogger(__name__)


def _next_friday(from_date: date | None = None) -> date:
    """Return the next Friday (or today if it's Friday)."""
    d = from_date or date.today()
    days_ahead = 4 - d.weekday()  # Friday = 4
    if days_ahead < 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def job_send_invites() -> None:
    """Monday 7 AM: Create the week and send invites to all active members."""
    friday = _next_friday()
    friday_str = friday.strftime("%b %d")
    logger.info(f"Sending invites for Friday {friday_str}")

    week = db.create_week(friday)
    members = db.get_active_members()

    sent = 0
    for member in members:
        if email_client.send_invite(member, friday_str):
            sent += 1

    logger.info(f"Sent {sent}/{len(members)} invite emails for week {friday}")


def job_send_reminders() -> None:
    """Wednesday 6 PM: Send reminders to non-respondents."""
    week = db.get_current_week()
    if not week:
        logger.warning("No open week found for reminders")
        return

    friday_str = date.fromisoformat(week.week_of).strftime("%b %d")
    non_respondents = db.get_non_respondents(week.id)
    registered = db.get_registrations(week.id, status="in")
    player_count = len(registered)

    sent = 0
    for member in non_respondents:
        if email_client.send_reminder(member, friday_str, player_count):
            sent += 1

    logger.info(
        f"Sent {sent}/{len(non_respondents)} reminder emails. "
        f"{player_count} players registered so far."
    )


def job_close_and_pair() -> None:
    """Thursday 12 PM: Close registration, generate pairings, send final emails."""
    week = db.get_current_week()
    if not week:
        logger.warning("No open week found for pairings")
        return

    friday = date.fromisoformat(week.week_of)
    friday_str = friday.strftime("%b %d")

    # Close the week
    db.close_week(week.id)
    logger.info(f"Closed registration for {friday_str}")

    # Get registered players
    players = db.get_registered_members(week.id)
    if not players:
        logger.info("No players registered. Skipping pairings.")
        return

    # Get tee times
    tee_times = db.get_tee_times(week.id)

    # Generate pairings
    groups = pairing_engine.generate_pairings(players, tee_times)
    logger.info(f"Generated {len(groups)} groups for {len(players)} players")

    # Save pairings to DB
    group_member_ids = [[p.id for p in g["players"]] for g in groups]
    tee_time_ids = [g["tee_time_id"] for g in groups]
    db.save_pairings(week.id, group_member_ids, tee_time_ids)

    # Format and send pairings emails
    course_info, groups_text = pairing_engine.format_pairings_text(groups, friday_str)

    sent = 0
    for player in players:
        if email_client.send_pairings(player, friday_str, course_info, groups_text):
            sent += 1

    logger.info(f"Sent pairings to {sent}/{len(players)} players")


def job_scrape_tee_times() -> None:
    """Wednesday 8 PM: Scrape Friday morning tee times from WebTrac."""
    friday = _next_friday()
    logger.info(f"Scraping tee times for Friday {friday}")
    try:
        saved = scraper.scrape_and_save(target_date=friday)
        logger.info(f"Scrape complete: {saved} tee times saved for {friday}")
    except Exception as e:
        logger.error(f"Tee time scrape failed: {e}")


def job_check_replies() -> None:
    """Poll Gmail for new replies and update registrations."""
    week = db.get_current_week()
    if not week:
        return

    replies = email_client.check_replies()
    for reply in replies:
        member = db.get_member_by_email(reply["email"])
        if member:
            db.upsert_registration(
                member.id, week.id, reply["status"],
                preferred_course=reply.get("preferred_course", ""),
                preferred_time=reply.get("preferred_time", ""),
            )
            prefs_str = ""
            if reply.get("preferred_course") or reply.get("preferred_time"):
                prefs_str = f" (prefers: {reply.get('preferred_course', '')} {reply.get('preferred_time', '')})"
            logger.info(
                f"Registered {member.name} as '{reply['status']}' for week {week.week_of}{prefs_str}"
            )
        else:
            logger.warning(f"Reply from unknown email: {reply['email']}")


def create_scheduler() -> BackgroundScheduler:
    """Create and configure the APScheduler with all jobs."""
    sched = BackgroundScheduler(timezone=config.TIMEZONE)

    # Monday 7:00 AM — send invites
    inv = config.SCHEDULE["invite"]
    sched.add_job(
        job_send_invites,
        "cron",
        day_of_week=inv["day_of_week"],
        hour=inv["hour"],
        minute=inv["minute"],
        id="send_invites",
        replace_existing=True,
    )

    # Wednesday 6:00 PM — send reminders
    rem = config.SCHEDULE["reminder"]
    sched.add_job(
        job_send_reminders,
        "cron",
        day_of_week=rem["day_of_week"],
        hour=rem["hour"],
        minute=rem["minute"],
        id="send_reminders",
        replace_existing=True,
    )

    # Wednesday 8:00 PM — scrape tee times
    scr = config.SCHEDULE["scrape"]
    sched.add_job(
        job_scrape_tee_times,
        "cron",
        day_of_week=scr["day_of_week"],
        hour=scr["hour"],
        minute=scr["minute"],
        id="scrape_tee_times",
        replace_existing=True,
    )

    # Thursday 12:00 PM — close and pair
    pair = config.SCHEDULE["pairings"]
    sched.add_job(
        job_close_and_pair,
        "cron",
        day_of_week=pair["day_of_week"],
        hour=pair["hour"],
        minute=pair["minute"],
        id="close_and_pair",
        replace_existing=True,
    )

    # Every 30 min (Mon–Thu) — check replies
    chk = config.SCHEDULE["check_replies"]
    sched.add_job(
        job_check_replies,
        "interval",
        minutes=chk["minutes"],
        id="check_replies",
        replace_existing=True,
    )

    return sched
