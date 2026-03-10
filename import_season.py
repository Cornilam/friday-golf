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
    (14, "2026-07-31", "Songbird Hills"),
    (15, "2026-08-07", "Morningstar"),
    (16, "2026-08-14", "Moor Downs"),
    (17, "2026-08-21", "Brown Deer"),
    (18, "2026-08-28", "Dretzka"),
    (19, "2026-09-04", "Oakwood"),
    (20, "2026-09-11", "Whitnall"),
    (21, "2026-09-18", "Currie"),
    (22, "2026-09-25", "Grant"),
]


# Hole-by-hole par and yardage data sourced from GolfPass
COURSE_DATA = [
    {"name": "Brown Deer", "num_holes": 18, "total_par": 71,
     "pars": "4,4,3,5,3,5,3,4,4,4,3,4,4,3,5,4,4,5",
     "yardages": "387,307,145,465,136,471,174,383,289,410,152,347,402,159,503,341,345,477"},
    {"name": "Dretzka", "num_holes": 18, "total_par": 72,
     "pars": "4,4,4,3,5,4,3,5,4,4,4,4,3,5,4,3,4,5",
     "yardages": "433,384,365,225,489,359,189,541,427,456,430,354,148,516,389,224,341,480"},
    {"name": "Oakwood", "num_holes": 18, "total_par": 72,
     "pars": "4,5,4,3,4,5,4,3,4,4,5,4,3,4,5,4,3,4",
     "yardages": ""},
    {"name": "Whitnall", "num_holes": 18, "total_par": 71,
     "pars": "4,4,3,4,4,3,5,4,4,4,4,5,4,4,3,4,4,4",
     "yardages": ""},
    {"name": "Currie", "num_holes": 18, "total_par": 71,
     "pars": "4,4,5,4,3,4,4,3,5,4,4,5,3,4,4,3,4,4",
     "yardages": ""},
    {"name": "Grant", "num_holes": 18, "total_par": 68,
     "pars": "4,4,4,4,3,4,3,3,4,4,4,4,4,4,3,4,3,5",
     "yardages": ""},
    {"name": "Greenfield", "num_holes": 18, "total_par": 69,
     "pars": "4,4,4,4,4,3,4,3,4,4,3,4,4,4,4,4,4,4",
     "yardages": "375,394,419,380,321,138,381,196,300,432,172,389,396,340,302,261,395,418"},
    {"name": "Lincoln", "num_holes": 9, "total_par": 33,
     "pars": "4,4,4,3,4,3,4,3,4",
     "yardages": "322,417,382,134,381,175,371,140,298"},
    {"name": "Hansen", "num_holes": 18, "total_par": 55,
     "pars": "3,3,3,3,3,3,3,3,4,3,3,3,3,3,3,3,3,3",
     "yardages": ""},
    {"name": "Warnimont", "num_holes": 18, "total_par": 54,
     "pars": "3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3",
     "yardages": "170,108,127,190,134,118,137,163,180,127,120,155,188,160,185,177,178,100"},
    {"name": "Brookfield Hills", "num_holes": 18, "total_par": 62,
     "pars": "4,3,4,3,3,4,4,4,3,4,4,3,3,3,4,3,3,3",
     "yardages": "375,215,405,175,195,400,380,425,230,390,360,150,165,215,325,135,180,205"},
    {"name": "Nagawaukee", "num_holes": 18, "total_par": 72,
     "pars": "4,5,3,4,4,5,4,3,4,4,5,4,3,5,4,3,4,4",
     "yardages": "415,552,202,436,369,514,355,175,409,412,502,381,229,542,372,179,435,351"},
    {"name": "Western Lakes", "num_holes": 18, "total_par": 72,
     "pars": "4,5,4,3,4,5,4,3,4,4,5,4,3,4,5,4,3,4",
     "yardages": ""},
    {"name": "Songbird Hills", "num_holes": 18, "total_par": 70,
     "pars": "4,4,3,4,4,4,3,4,5,5,3,4,4,5,4,3,3,4",
     "yardages": ""},
    {"name": "Morningstar", "num_holes": 18, "total_par": 72,
     "pars": "5,4,3,4,3,4,5,4,4,4,3,5,4,3,4,4,4,5",
     "yardages": ""},
    {"name": "Moor Downs", "num_holes": 9, "total_par": 35,
     "pars": "4,4,3,4,4,4,3,4,5",
     "yardages": "332,345,178,320,280,380,127,301,451"},
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

    print("\nImporting course data...")
    for c in COURSE_DATA:
        db.upsert_course(c["name"], c["num_holes"], c["total_par"], c["pars"], c["yardages"])
        print(f"  {c['name']}: {c['num_holes']}H, par {c['total_par']}")

    print("\nDone!")


if __name__ == "__main__":
    import_all()
