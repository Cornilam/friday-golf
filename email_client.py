"""Gmail API wrapper for sending and reading emails."""

import base64
import logging
import re
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
import db

logger = logging.getLogger(__name__)


def get_gmail_service():
    """Authenticate and return a Gmail API service instance."""
    creds = None
    token_path = Path(config.GMAIL_TOKEN_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), config.SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_FILE, config.SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str, email_type: str) -> bool:
    """Send an email via Gmail API and log it."""
    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message["to"] = to
        message["from"] = config.FROM_EMAIL
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        db.log_email(to, subject, email_type)
        logger.info(f"Sent {email_type} email to {to}")
        return True

    except HttpError as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def send_invite(member: db.Member, friday_date: str) -> bool:
    """Send the Monday invite email to a member."""
    template = Path("templates/invite.txt").read_text()
    body = template.format(name=member.name, date=friday_date)
    subject = f"Friday Golf -- Who's In? ({friday_date})"
    return send_email(member.email, subject, body, "invite")


def send_reminder(member: db.Member, friday_date: str, player_count: int) -> bool:
    """Send the Wednesday reminder to a non-respondent."""
    template = Path("templates/reminder.txt").read_text()
    body = template.format(
        name=member.name, date=friday_date, player_count=player_count
    )
    subject = f"Friday Golf Reminder -- We Need Your RSVP ({friday_date})"
    return send_email(member.email, subject, body, "reminder")


def send_pairings(
    member: db.Member, friday_date: str, course_info: str, groups_text: str
) -> bool:
    """Send the Thursday pairings email."""
    template = Path("templates/pairings.txt").read_text()
    body = template.format(
        date=friday_date, course_info=course_info, groups=groups_text
    )
    subject = f"Friday Golf Pairings -- You're On! ({friday_date})"
    return send_email(member.email, subject, body, "pairings")


def _clean_reply_text(body: str) -> str:
    """Extract the reply text before any quoted content."""
    lines = []
    for line in body.strip().splitlines():
        if line.startswith(">") or (line.startswith("On ") and "wrote:" in line):
            break
        lines.append(line)
    text = " ".join(lines).lower().strip()
    text = re.sub(r"<[^>]+>", "", text)  # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_reply_status(body: str) -> Optional[str]:
    """Parse an email reply body to determine RSVP status.

    Returns 'in', 'out', or None if unclear.
    """
    text = _clean_reply_text(body)
    if not text:
        return None

    for keyword in config.KEYWORDS_IN:
        if keyword in text:
            return "in"

    for keyword in config.KEYWORDS_OUT:
        if keyword in text:
            return "out"

    return None


def parse_reply_preferences(body: str) -> dict:
    """Parse course and time preferences from a reply.

    Handles replies like:
      "IN - Brown Deer, 8am"
      "in. currie 9:30am"
      "I'm in, prefer Dretzka morning"

    Returns {'course': str, 'time': str} (empty strings if not found).
    """
    text = _clean_reply_text(body)
    if not text:
        return {"course": "", "time": ""}

    # Match course names from config
    matched_course = ""
    for course_name in config.COURSES:
        if course_name.lower() in text:
            matched_course = course_name
            break

    # Match time patterns: "8am", "9:30am", "10:00 am", "morning", "afternoon"
    matched_time = ""
    time_match = re.search(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)", text)
    if time_match:
        matched_time = time_match.group().strip()
    elif "morning" in text:
        matched_time = "morning"
    elif "afternoon" in text:
        matched_time = "afternoon"
    elif "early" in text:
        matched_time = "early"
    elif "late" in text:
        matched_time = "late"

    return {"course": matched_course, "time": matched_time}


def check_replies() -> list[dict]:
    """Check Gmail inbox for new replies to invite/reminder emails.

    Returns a list of {'email': str, 'status': str} for successfully parsed replies.
    """
    try:
        service = get_gmail_service()

        # Search for unread replies to our golf emails
        query = 'is:unread subject:"Friday Golf"'
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=50)
            .execute()
        )
        messages = results.get("messages", [])

        parsed_replies = []
        for msg_meta in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_meta["id"], format="full")
                .execute()
            )

            # Extract sender email
            headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
            from_header = headers.get("from", "")
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", from_header)
            if not email_match:
                continue
            sender_email = email_match.group().lower()

            # Skip our own outgoing emails (but allow replies from ourselves)
            subject = headers.get("subject", "")
            is_reply = subject.lower().startswith("re:")
            if sender_email == config.FROM_EMAIL.lower() and not is_reply:
                continue

            # Extract body text
            body = _extract_body(msg["payload"])
            if not body:
                continue

            status = parse_reply_status(body)
            prefs = parse_reply_preferences(body) if status == "in" else {"course": "", "time": ""}

            if status:
                parsed_replies.append({
                    "email": sender_email,
                    "status": status,
                    "preferred_course": prefs["course"],
                    "preferred_time": prefs["time"],
                })
                logger.info(
                    f"Parsed reply from {sender_email}: {status}"
                    + (f" (course={prefs['course']}, time={prefs['time']})" if prefs["course"] or prefs["time"] else "")
                )
            else:
                logger.warning(f"Unclear reply from {sender_email}: {body[:100]}")
                # Send clarification
                member = db.get_member_by_email(sender_email)
                if member:
                    send_email(
                        sender_email,
                        "Re: Friday Golf -- Quick Clarification",
                        f"Hey {member.name},\n\nI couldn't tell if you're in or out. "
                        "Could you reply with just IN or OUT?\n\n-- Friday Golf Bot",
                        "clarification",
                    )

            # Mark as read
            service.users().messages().modify(
                userId="me",
                id=msg_meta["id"],
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

        return parsed_replies

    except HttpError as e:
        logger.error(f"Error checking replies: {e}")
        return []


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text

    # Fallback: try the body directly
    if "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    return ""
