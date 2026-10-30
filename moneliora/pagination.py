"""Bounded keyset pages. Cursors are positions, never authentication tokens."""
import base64
from datetime import datetime
import json
import re
from fastapi import HTTPException


def page(rows, limit):
    selected = rows[:limit]
    more = len(rows) > limit
    return selected, {'has_more': more, 'next_cursor': selected[-1]['id'] if more else None,
                      'limit': limit}


def pilot_cursor(row):
    raw = json.dumps([row['created_at'], row['id']], separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def decode_pilot_cursor(cursor):
    try:
        raw = base64.b64decode(cursor + '=' * (-len(cursor) % 4), altchars=b'-_', validate=True)
        created, identifier = json.loads(raw)
        if not isinstance(created, str) or not isinstance(identifier, str):
            raise ValueError()
        parsed = datetime.fromisoformat(created)
        if parsed.tzinfo is None or not re.fullmatch(r'[a-f0-9]{32}', identifier):
            raise ValueError()
        return created, identifier
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(422, 'Invalid pagination cursor.') from None
