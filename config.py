"""Configuration for Friday Golf system."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "friday_golf.db"))
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
GMAIL_TOKEN_FILE = "token.json"

# Email
FROM_EMAIL = os.getenv("FROM_EMAIL", "yourgolf@gmail.com")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Scheduling (America/Chicago for Milwaukee area)
TIMEZONE = os.getenv("TIMEZONE", "America/Chicago")

SCHEDULE = {
    "invite": {"day_of_week": "mon", "hour": 7, "minute": 0},
    "reminder": {"day_of_week": "wed", "hour": 18, "minute": 0},
    "scrape": {"day_of_week": "wed", "hour": 20, "minute": 0},
    "pairings": {"day_of_week": "thu", "hour": 12, "minute": 0},
    "check_replies": {"minutes": 30},  # polling interval
}

# Pairing
TEE_TIME_INTERVAL = int(os.getenv("TEE_TIME_INTERVAL", "8"))

# WebTrac tee time scraping — Milwaukee County Parks
WEBTRAC_BASE_URL = "https://wimilwaukeectyweb.myvscloud.com/webtrac/web/search.html"
SCRAPE_MORNING_CUTOFF = "12:00"  # only keep tee times before noon
PREFERRED_HOLES = 18
PREFERRED_PLAYERS = 4

# Milwaukee County golf courses — secondarycode values for WebTrac.
# Verified from the live WebTrac course dropdown.
COURSES = {
    "Brown Deer": "1",
    "Dretzka": "2",
    "Oakwood": "3",
    "Whitnall": "4",
    "Currie": "5",
    "Grant": "6",
    "Greenfield": "7",
    "Lincoln": "8",
    "Hansen": "9",
    "Warnimont": "10",
    "Lake": "12",
    "Noyes": "14",
    "Zablocki": "15",
}

# WebTrac login credentials (for booking)
WEBTRAC_USERNAME = os.getenv("WEBTRAC_USERNAME", "")
WEBTRAC_PASSWORD = os.getenv("WEBTRAC_PASSWORD", "")

# RSVP link tokens
RSVP_SECRET = os.getenv("RSVP_SECRET", "friday-golf-rsvp-default-key")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

# Reply keyword matching
KEYWORDS_IN = {"in", "yes", "i'm in", "count me in", "playing", "im in", "i am in"}
KEYWORDS_OUT = {"out", "no", "can't", "cant", "skip", "not this week", "pass", "nope"}
