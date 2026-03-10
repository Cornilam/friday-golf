"""SQLite database setup and queries for Friday Golf."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from config import DB_PATH

# --- Dataclasses ---


@dataclass
class Member:
    id: int
    name: str
    email: str
    active: bool
    created_at: str


@dataclass
class Week:
    id: int
    week_of: str  # the Friday date
    status: str  # open, closed, cancelled
    created_at: str


@dataclass
class Registration:
    id: int
    member_id: int
    week_id: int
    status: str  # in, out
    preferred_course: str
    preferred_time: str
    registered_at: str


@dataclass
class TeeTime:
    id: int
    week_id: int
    course_name: str
    course_code: str
    tee_time: str  # datetime string
    holes: int
    price_display: str
    spots: int
    source_url: str
    scraped_at: Optional[str]


@dataclass
class Pairing:
    id: int
    week_id: int
    group_number: int
    member_id: int
    tee_time_id: Optional[int]


@dataclass
class Course:
    id: int
    name: str
    num_holes: int
    total_par: int
    pars: str  # comma-separated, e.g. "4,4,3,5,..."
    yardages: str  # comma-separated or empty

    def par_list(self) -> list[int]:
        return [int(p) for p in self.pars.split(",")]

    def yardage_list(self) -> list[int]:
        if not self.yardages:
            return []
        return [int(y) for y in self.yardages.split(",")]


@dataclass
class Scorecard:
    id: int
    member_id: int
    week_id: int
    course_id: int
    scores: str  # comma-separated, e.g. "5,4,3,6,..."
    total_score: int
    score_vs_par: int
    submitted_by: Optional[int]
    submitted_at: str

    def score_list(self) -> list[int]:
        return [int(s) for s in self.scores.split(",")]


@dataclass
class EmailLogEntry:
    id: int
    to_email: str
    subject: str
    email_type: str
    sent_at: str


# --- Database connection ---


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            active BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS weeks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_of TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL REFERENCES members(id),
            week_id INTEGER NOT NULL REFERENCES weeks(id),
            status TEXT NOT NULL,
            preferred_course TEXT NOT NULL DEFAULT '',
            preferred_time TEXT NOT NULL DEFAULT '',
            registered_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(member_id, week_id)
        );

        CREATE TABLE IF NOT EXISTS tee_times (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_id INTEGER NOT NULL REFERENCES weeks(id),
            course_name TEXT NOT NULL,
            course_code TEXT NOT NULL DEFAULT '',
            tee_time TEXT NOT NULL,
            holes INTEGER NOT NULL DEFAULT 18,
            price_display TEXT NOT NULL DEFAULT '',
            spots INTEGER NOT NULL DEFAULT 4,
            source_url TEXT NOT NULL DEFAULT '',
            scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS pairings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_id INTEGER NOT NULL REFERENCES weeks(id),
            group_number INTEGER NOT NULL,
            member_id INTEGER NOT NULL REFERENCES members(id),
            tee_time_id INTEGER REFERENCES tee_times(id)
        );

        CREATE TABLE IF NOT EXISTS season_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_number INTEGER NOT NULL,
            play_date TEXT NOT NULL,
            course_name TEXT NOT NULL,
            UNIQUE(week_number)
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            num_holes INTEGER NOT NULL,
            total_par INTEGER NOT NULL,
            pars TEXT NOT NULL,
            yardages TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS scorecards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL REFERENCES members(id),
            week_id INTEGER NOT NULL REFERENCES weeks(id),
            course_id INTEGER NOT NULL REFERENCES courses(id),
            scores TEXT NOT NULL,
            total_score INTEGER NOT NULL,
            score_vs_par INTEGER NOT NULL,
            submitted_by INTEGER REFERENCES members(id),
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(member_id, week_id)
        );

        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            email_type TEXT NOT NULL,
            sent_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Migrations — add columns to existing tables if missing
    _migrate(conn)
    conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add new columns to existing tables (safe to run repeatedly)."""
    # Add preference columns to registrations
    cols = {row[1] for row in conn.execute("PRAGMA table_info(registrations)").fetchall()}
    if "preferred_course" not in cols:
        conn.execute("ALTER TABLE registrations ADD COLUMN preferred_course TEXT NOT NULL DEFAULT ''")
    if "preferred_time" not in cols:
        conn.execute("ALTER TABLE registrations ADD COLUMN preferred_time TEXT NOT NULL DEFAULT ''")
    conn.commit()


# --- Member queries ---


def add_member(name: str, email: str) -> Member:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO members (name, email) VALUES (?, ?)", (name, email.lower())
    )
    member_id = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    conn.close()
    return Member(**row)


def deactivate_member(email: str) -> bool:
    conn = get_connection()
    cursor = conn.execute(
        "UPDATE members SET active = 0 WHERE email = ? AND active = 1",
        (email.lower(),),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed


def get_active_members() -> list[Member]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM members WHERE active = 1 ORDER BY name"
    ).fetchall()
    conn.close()
    return [Member(**r) for r in rows]


def get_member_by_email(email: str) -> Optional[Member]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM members WHERE email = ? AND active = 1", (email.lower(),)
    ).fetchone()
    conn.close()
    return Member(**row) if row else None


# --- Week queries ---


def create_week(friday: date) -> Week:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT OR IGNORE INTO weeks (week_of) VALUES (?)", (friday.isoformat(),)
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM weeks WHERE week_of = ?", (friday.isoformat(),)
    ).fetchone()
    conn.close()
    return Week(**row)


def get_current_week() -> Optional[Week]:
    """Get the most recent open week, or the upcoming one."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM weeks WHERE status = 'open' ORDER BY week_of DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return Week(**row) if row else None


def close_week(week_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE weeks SET status = 'closed' WHERE id = ?", (week_id,))
    conn.commit()
    conn.close()


# --- Registration queries ---


def upsert_registration(
    member_id: int, week_id: int, status: str,
    preferred_course: str = "", preferred_time: str = "",
) -> Registration:
    conn = get_connection()
    conn.execute(
        """INSERT INTO registrations (member_id, week_id, status, preferred_course, preferred_time)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(member_id, week_id)
           DO UPDATE SET status = excluded.status,
               preferred_course = excluded.preferred_course,
               preferred_time = excluded.preferred_time,
               registered_at = datetime('now')""",
        (member_id, week_id, status, preferred_course, preferred_time),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM registrations WHERE member_id = ? AND week_id = ?",
        (member_id, week_id),
    ).fetchone()
    conn.close()
    return Registration(**row)


def get_registrations(week_id: int, status: Optional[str] = None) -> list[Registration]:
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM registrations WHERE week_id = ? AND status = ?",
            (week_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM registrations WHERE week_id = ?", (week_id,)
        ).fetchall()
    conn.close()
    return [Registration(**r) for r in rows]


def get_registered_members(week_id: int) -> list[Member]:
    """Get all members who RSVP'd 'in' for a given week."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT m.* FROM members m
           JOIN registrations r ON m.id = r.member_id
           WHERE r.week_id = ? AND r.status = 'in' AND m.active = 1
           ORDER BY m.name""",
        (week_id,),
    ).fetchall()
    conn.close()
    return [Member(**r) for r in rows]


def get_non_respondents(week_id: int) -> list[Member]:
    """Get active members who haven't responded for a given week."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT m.* FROM members m
           WHERE m.active = 1
           AND m.id NOT IN (
               SELECT member_id FROM registrations WHERE week_id = ?
           )
           ORDER BY m.name""",
        (week_id,),
    ).fetchall()
    conn.close()
    return [Member(**r) for r in rows]


# --- Tee time queries ---


def add_tee_time(
    week_id: int,
    course_name: str,
    tee_time: datetime,
    holes: int = 18,
    price_display: str = "",
    spots: int = 4,
    course_code: str = "",
    source_url: str = "",
    scraped_at: Optional[datetime] = None,
) -> TeeTime:
    conn = get_connection()
    scraped_str = scraped_at.isoformat() if scraped_at else None
    cursor = conn.execute(
        """INSERT INTO tee_times
           (week_id, course_name, course_code, tee_time, holes, price_display, spots, source_url, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (week_id, course_name, course_code, tee_time.isoformat(), holes, price_display, spots, source_url, scraped_str),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM tee_times WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    conn.close()
    return TeeTime(**row)


def get_tee_times(week_id: int) -> list[TeeTime]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tee_times WHERE week_id = ? ORDER BY tee_time",
        (week_id,),
    ).fetchall()
    conn.close()
    return [TeeTime(**r) for r in rows]


def clear_scraped_tee_times(week_id: int) -> int:
    """Remove previously scraped tee times for a week (keeps manually added ones)."""
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM tee_times WHERE week_id = ? AND scraped_at IS NOT NULL",
        (week_id,),
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted


# --- Pairing queries ---


def save_pairings(
    week_id: int, groups: list[list[int]], tee_time_ids: list[Optional[int]]
) -> None:
    """Save pairing groups. groups is a list of lists of member_ids."""
    conn = get_connection()
    # Clear any existing pairings for this week
    conn.execute("DELETE FROM pairings WHERE week_id = ?", (week_id,))
    for group_num, member_ids in enumerate(groups, start=1):
        tee_time_id = tee_time_ids[group_num - 1] if group_num - 1 < len(tee_time_ids) else None
        for member_id in member_ids:
            conn.execute(
                """INSERT INTO pairings (week_id, group_number, member_id, tee_time_id)
                   VALUES (?, ?, ?, ?)""",
                (week_id, group_num, member_id, tee_time_id),
            )
    conn.commit()
    conn.close()


def get_pairings(week_id: int) -> list[dict]:
    """Get pairings grouped by group_number with member names and tee time info."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.group_number, m.name, m.email, t.course_name, t.tee_time
           FROM pairings p
           JOIN members m ON p.member_id = m.id
           LEFT JOIN tee_times t ON p.tee_time_id = t.id
           WHERE p.week_id = ?
           ORDER BY p.group_number, m.name""",
        (week_id,),
    ).fetchall()
    conn.close()

    groups: dict[int, dict] = {}
    for row in rows:
        gn = row["group_number"]
        if gn not in groups:
            groups[gn] = {
                "group_number": gn,
                "players": [],
                "course_name": row["course_name"],
                "tee_time": row["tee_time"],
            }
        groups[gn]["players"].append({"name": row["name"], "email": row["email"]})

    return [groups[k] for k in sorted(groups)]


# --- Season schedule ---


def upsert_season_week(week_number: int, play_date: str, course_name: str) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO season_schedule (week_number, play_date, course_name)
           VALUES (?, ?, ?)
           ON CONFLICT(week_number)
           DO UPDATE SET play_date = excluded.play_date, course_name = excluded.course_name""",
        (week_number, play_date, course_name),
    )
    conn.commit()
    conn.close()


def get_season_schedule() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM season_schedule ORDER BY week_number"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Course queries ---


def upsert_course(name: str, num_holes: int, total_par: int, pars: str, yardages: str = "") -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO courses (name, num_holes, total_par, pars, yardages)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(name)
           DO UPDATE SET num_holes = excluded.num_holes,
               total_par = excluded.total_par,
               pars = excluded.pars,
               yardages = excluded.yardages""",
        (name, num_holes, total_par, pars, yardages),
    )
    conn.commit()
    conn.close()


def get_course_by_name(name: str) -> Optional[Course]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM courses WHERE name = ?", (name,)).fetchone()
    conn.close()
    return Course(**row) if row else None


def get_all_courses() -> list[Course]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM courses ORDER BY name").fetchall()
    conn.close()
    return [Course(**r) for r in rows]


def get_course_for_week(week_id: int) -> Optional[Course]:
    """Look up the scheduled course for a week via season_schedule."""
    conn = get_connection()
    week_row = conn.execute("SELECT week_of FROM weeks WHERE id = ?", (week_id,)).fetchone()
    if not week_row:
        conn.close()
        return None
    sched_row = conn.execute(
        "SELECT course_name FROM season_schedule WHERE play_date = ?",
        (week_row["week_of"],),
    ).fetchone()
    if not sched_row:
        conn.close()
        return None
    course_row = conn.execute(
        "SELECT * FROM courses WHERE name = ?", (sched_row["course_name"],)
    ).fetchone()
    conn.close()
    return Course(**course_row) if course_row else None


# --- Scorecard queries ---


def upsert_scorecard(
    member_id: int, week_id: int, course_id: int,
    scores: str, total_score: int, score_vs_par: int,
    submitted_by: Optional[int] = None,
) -> Scorecard:
    conn = get_connection()
    conn.execute(
        """INSERT INTO scorecards (member_id, week_id, course_id, scores, total_score, score_vs_par, submitted_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(member_id, week_id)
           DO UPDATE SET course_id = excluded.course_id,
               scores = excluded.scores,
               total_score = excluded.total_score,
               score_vs_par = excluded.score_vs_par,
               submitted_by = excluded.submitted_by,
               submitted_at = datetime('now')""",
        (member_id, week_id, course_id, scores, total_score, score_vs_par, submitted_by),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM scorecards WHERE member_id = ? AND week_id = ?",
        (member_id, week_id),
    ).fetchone()
    conn.close()
    return Scorecard(**row)


def get_scorecards_for_week(week_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT sc.*, m.name AS member_name, c.name AS course_name,
                  c.total_par, c.pars AS course_pars, c.num_holes
           FROM scorecards sc
           JOIN members m ON sc.member_id = m.id
           JOIN courses c ON sc.course_id = c.id
           WHERE sc.week_id = ?
           ORDER BY sc.total_score""",
        (week_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_season_leaderboard() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT m.id, m.name,
                  COUNT(sc.id) AS rounds_played,
                  SUM(sc.total_score) AS total_strokes,
                  SUM(sc.score_vs_par) AS total_vs_par,
                  ROUND(AVG(sc.total_score), 1) AS avg_score,
                  ROUND(AVG(sc.score_vs_par), 1) AS avg_vs_par,
                  MIN(sc.total_score) AS best_round,
                  MAX(sc.total_score) AS worst_round
           FROM scorecards sc
           JOIN members m ON sc.member_id = m.id
           GROUP BY m.id
           ORDER BY avg_vs_par ASC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_player_scorecards(member_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT sc.*, c.name AS course_name, c.total_par, c.pars AS course_pars,
                  c.num_holes, w.week_of
           FROM scorecards sc
           JOIN courses c ON sc.course_id = c.id
           JOIN weeks w ON sc.week_id = w.id
           WHERE sc.member_id = ?
           ORDER BY w.week_of""",
        (member_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Email log ---


def log_email(to_email: str, subject: str, email_type: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO email_log (to_email, subject, email_type) VALUES (?, ?, ?)",
        (to_email, subject, email_type),
    )
    conn.commit()
    conn.close()
