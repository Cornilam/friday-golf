"""Flask web dashboard for Friday Golf."""

import logging
import threading
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

import config
import db
import email_client
import pairing_engine
import scraper
import scheduler as sched

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "friday-golf-secret"

db.init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_week_context():
    """Build template context for the current week."""
    week = db.get_current_week()
    if not week:
        return {"week": None}

    friday = date.fromisoformat(week.week_of)
    regs = db.get_registrations(week.id)
    ins = [r for r in regs if r.status == "in"]
    outs = [r for r in regs if r.status == "out"]
    non_resp = db.get_non_respondents(week.id)
    tee_times = db.get_tee_times(week.id)
    pairings = db.get_pairings(week.id)

    # Resolve member names and preferences for registrations
    conn = db.get_connection()
    in_members = []
    for r in ins:
        row = conn.execute("SELECT name, email FROM members WHERE id = ?", (r.member_id,)).fetchone()
        if row:
            in_members.append({
                "name": row["name"],
                "email": row["email"],
                "preferred_course": r.preferred_course,
                "preferred_time": r.preferred_time,
            })
    out_members = []
    for r in outs:
        row = conn.execute("SELECT name, email FROM members WHERE id = ?", (r.member_id,)).fetchone()
        if row:
            out_members.append({"name": row["name"], "email": row["email"]})
    conn.close()

    return {
        "week": week,
        "friday": friday,
        "friday_str": friday.strftime("%B %d, %Y"),
        "in_members": in_members,
        "out_members": out_members,
        "non_resp": non_resp,
        "tee_times": tee_times,
        "pairings": pairings,
        "total_in": len(ins),
        "total_out": len(outs),
        "total_no_resp": len(non_resp),
    }


def _run_in_thread(fn, *args):
    """Run a function in a background thread."""
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    ctx = _get_week_context()
    members = db.get_active_members()
    return render_template("dashboard.html", **ctx, members=members, courses=config.COURSES)


@app.route("/action/send-invites", methods=["POST"])
def action_send_invites():
    try:
        sched.job_send_invites()
        flash("Invites sent!", "success")
    except Exception as e:
        flash(f"Error sending invites: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/action/check-replies", methods=["POST"])
def action_check_replies():
    try:
        sched.job_check_replies()
        flash("Replies checked.", "success")
    except Exception as e:
        flash(f"Error checking replies: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/action/send-reminders", methods=["POST"])
def action_send_reminders():
    try:
        sched.job_send_reminders()
        flash("Reminders sent!", "success")
    except Exception as e:
        flash(f"Error sending reminders: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/action/scrape-times", methods=["POST"])
def action_scrape_times():
    try:
        saved = scraper.scrape_and_save()
        flash(f"Scraped {saved} tee times.", "success")
    except Exception as e:
        flash(f"Scrape failed: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/action/generate-pairings", methods=["POST"])
def action_generate_pairings():
    try:
        sched.job_close_and_pair()
        flash("Pairings generated and sent!", "success")
    except Exception as e:
        flash(f"Error generating pairings: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/action/add-member", methods=["POST"])
def action_add_member():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    if not name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("dashboard"))
    try:
        db.add_member(name, email)
        flash(f"Added {name}.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/action/remove-member", methods=["POST"])
def action_remove_member():
    email = request.form.get("email", "").strip()
    if db.deactivate_member(email):
        flash(f"Removed {email}.", "success")
    else:
        flash(f"Member not found: {email}", "error")
    return redirect(url_for("dashboard"))


@app.route("/action/add-tee-time", methods=["POST"])
def action_add_tee_time():
    from datetime import datetime
    course = request.form.get("course", "").strip()
    time_str = request.form.get("time", "").strip()
    spots = int(request.form.get("spots", 4))

    week = db.get_current_week()
    if not week:
        flash("No open week.", "error")
        return redirect(url_for("dashboard"))
    try:
        tee_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        db.add_tee_time(week.id, course, tee_dt, spots=spots)
        flash(f"Added tee time: {course} at {time_str}", "success")
    except ValueError:
        flash("Invalid time format. Use YYYY-MM-DD HH:MM.", "error")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
