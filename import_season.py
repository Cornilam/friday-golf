"""Import season data from the Jacobs Golf Signup spreadsheet."""

import db


# Parsed from '2026 Jacobs Golf Signup.xlsx'
MEMBERS = [
    "Brad Blum",
    "Scott Wendt",
    "Cornelius Nilam",
    "Ian Frost",
    "Thomas Erickson",
    "Dan Lakich",
    "Gary Ferguson",
    "Kyle Peschel",
    "Glen McGinn",
    "Scott Stevenson",
    "Kevin Brusso",
    "Jeff Bauer",
]

SEASON = [
    (1, "2026-05-01", "Brown Deer"),
    (2, "2026-05-08", "Dretzka"),
    (3, "2026-05-15", "Oakwood"),
    (4, "2026-05-22", "Whitnall"),
    (5, "2026-05-29", "Currie"),
    (6, "2026-06-05", "Grant"),
    (7, "2026-06-12", "Greenfield"),
    (8, "2026-06-19", "Lincoln"),
    (9, "2026-06-26", "Hansen"),
    (10, "2026-07-03", "Warnimont"),
    (11, "2026-07-10", "Brookfield Hills"),
    (12, "2026-07-17", "Nagawaukee"),
    (13, "2026-07-24", "Western Lakes"),
    (14, "2026-07-31", "Songbird"),
    (15, "2026-08-07", "Morningstar"),
    (16, "2026-08-14", "Moor Downs"),
    (17, "2026-08-21", "Brown Deer"),
    (18, "2026-08-28", "Dretzka"),
    (19, "2026-09-04", "Oakwood"),
    (20, "2026-09-11", "Whitnall"),
    (21, "2026-09-18", "Currie"),
    (22, "2026-09-25", "Grant"),
]


def import_all():
    db.init_db()

    print("Importing members...")
    for name in MEMBERS:
        # Use a placeholder email — update later with real emails
        email = name.lower().replace(" ", ".") + "@fridaygolf.local"
        try:
            member = db.add_member(name, email)
            print(f"  Added {member.name}")
        except Exception:
            print(f"  {name} already exists, skipping")

    print("\nImporting season schedule...")
    for week_num, play_date, course in SEASON:
        db.upsert_season_week(week_num, play_date, course)
        print(f"  Week {week_num}: {play_date} — {course}")

    print("\nDone!")


if __name__ == "__main__":
    import_all()
