# Friday Golf

Automated weekly golf coordination that runs entirely through email. Scrapes tee times from Milwaukee County Parks' WebTrac booking system and coordinates a Friday morning golf group.

## How It Works

| Day | Time | Action |
|-----|------|--------|
| Monday | 7:00 AM | Sends invite email to all members |
| Mon–Thu | Every 30 min | Polls Gmail for RSVP replies |
| Wednesday | 6:00 PM | Sends reminder to non-respondents |
| Wednesday | 8:00 PM | Scrapes Friday morning tee times from WebTrac |
| Thursday | 12:00 PM | Closes registration, generates pairings, sends final email |

Members reply **IN** or **OUT** to the invite email. The system parses replies with keyword matching and generates random groups of 4.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Gmail API**
4. Create **OAuth 2.0 credentials** (Desktop application)
5. Download the credentials JSON file and save it as `credentials.json` in the project root

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

- `GMAIL_CREDENTIALS_FILE` — path to your OAuth credentials JSON
- `FROM_EMAIL` — the Gmail address to send from
- `TIMEZONE` — defaults to `America/Chicago` (Milwaukee area)

### 4. Verify course codes

The WebTrac scraper needs the `secondarycode` for each Milwaukee County course. The placeholder values in `config.py` need to be verified:

1. Visit the WebTrac search page in your browser
2. Select each course from the dropdown
3. Note the `secondarycode=N` value in the URL
4. Update the `COURSES` dict in `config.py` with the correct codes

### 5. Initialize the database

```bash
python cli.py list-members
```

This automatically creates `friday_golf.db` on first run.

### 6. Add members

```bash
python cli.py add-member "Alice Smith" alice@example.com
python cli.py add-member "Bob Jones" bob@example.com
```

### 7. Test the scraper

```bash
python cli.py scrape-times
```

This runs the Playwright scraper against WebTrac for the next Friday. Check the output and adjust selectors in `scraper.py` if the site structure differs from what's expected.

### 8. First-time Gmail auth

```bash
python cli.py trigger-invite
```

This opens a browser window for OAuth consent on first run. After authorizing, a `token.json` file is saved for future use.

## Running

### Start the scheduler (runs continuously)

```bash
python main.py
```

### CLI commands

```bash
python cli.py add-member "Name" email@example.com   # Add a member
python cli.py remove-member email@example.com        # Deactivate a member
python cli.py list-members                           # Show active members
python cli.py add-tee-time "Course" "2025-03-14 08:00" --spots 4  # Manual fallback
python cli.py scrape-times                           # Scrape tee times from WebTrac
python cli.py scrape-times --date 2025-06-20         # Scrape for a specific date
python cli.py list-times                             # Show tee times for current week
python cli.py trigger-invite                         # Manually send invites
python cli.py trigger-reminders                      # Manually send reminders
python cli.py trigger-pairings                       # Manually close + send pairings
python cli.py check-replies                          # Manually check inbox
python cli.py status                                 # Show current week status
```

## Tee Time Scraper

The scraper targets Milwaukee County Parks' WebTrac system, which is fully JavaScript-rendered. It uses Playwright (headless Chromium) to:

1. Navigate to the search page with pre-filled parameters (course, date, players, holes)
2. Wait for JS-rendered results to load
3. Parse available tee time slots (time, price, availability)
4. Filter to morning times only (before noon)
5. Save results to the database

**Important notes:**
- Tee times can only be booked 7 days in advance, so scraping happens Wednesday evening
- The scraper has retry logic (3 attempts per course) for reliability
- If scraping fails, use `add-tee-time` CLI command as a manual fallback
- Weekend tee times before 11am at Brown Deer, Dretzka, Oakwood, Currie, Grant, and Greenfield are 18-hole only

## Testing

```bash
python -m pytest tests/ -v
```

## Project Structure

```
friday-golf/
├── main.py              # Entry point: starts scheduler
├── cli.py               # Admin CLI commands
├── config.py            # Settings, course codes, WebTrac config
├── db.py                # SQLite schema and queries
├── email_client.py      # Gmail API: send, read, parse replies
├── scraper.py           # Playwright-based WebTrac tee time scraper
├── pairing_engine.py    # Random group generation
├── scheduler.py         # APScheduler job definitions
├── templates/
│   ├── invite.txt       # Monday invite email
│   ├── reminder.txt     # Wednesday reminder email
│   └── pairings.txt     # Thursday pairings email
└── tests/
    └── test_pairing_engine.py
```
