"""RSVP token generation and validation.

Tokens are HMAC-signed with itsdangerous (bundled with Flask) and encode
member_id + week_id.  No database table needed -- validation simply
recomputes the signature.
"""

from itsdangerous import URLSafeSerializer, BadSignature

import config


def generate_rsvp_token(member_id: int, week_id: int) -> str:
    """Create a signed RSVP token encoding member_id and week_id."""
    s = URLSafeSerializer(config.RSVP_SECRET)
    return s.dumps({"m": member_id, "w": week_id})


def validate_rsvp_token(token: str) -> dict | None:
    """Validate and decode an RSVP token.

    Returns {"m": member_id, "w": week_id} or None if invalid.
    """
    s = URLSafeSerializer(config.RSVP_SECRET)
    try:
        return s.loads(token)
    except BadSignature:
        return None
