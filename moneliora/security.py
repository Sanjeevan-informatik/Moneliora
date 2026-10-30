"""Durable authentication throttles and audit events; never log credentials."""
from hashlib import sha256
import math
import time

from fastapi import HTTPException
from moneliora.database import connect_database

WINDOW_SECONDS = 900
AUDIT_RETENTION_SECONDS = 30 * 86400
SCHEMA = '''
CREATE TABLE IF NOT EXISTS auth_limits (
    bucket TEXT PRIMARY KEY, started_at INTEGER NOT NULL, attempts INTEGER NOT NULL,
    reported INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS auth_limits_expiry ON auth_limits(started_at);
CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at INTEGER NOT NULL,
    event TEXT NOT NULL, user_id INTEGER, subject_hash TEXT, client_hash TEXT
);
CREATE INDEX IF NOT EXISTS security_events_expiry ON security_events(occurred_at);
'''


def digest(value):
    return sha256(value.encode('utf-8')).hexdigest()


def record(db, event, *, user_id=None, email=None, client=None):
    db.execute('''INSERT INTO security_events(occurred_at,event,user_id,subject_hash,client_hash)
                  VALUES(?,?,?,?,?)''',
               (int(time.time()), event, user_id, digest(email) if email else None,
                digest(client) if client else None))


def cleanup(db):
    now = int(time.time())
    db.execute('DELETE FROM auth_limits WHERE started_at<=?', (now-WINDOW_SECONDS,))
    db.execute('DELETE FROM security_events WHERE occurred_at<?', (now-AUDIT_RETENTION_SECONDS,))


def throttle(path, action, client, email=None):
    """Count attempts across workers, independently by IP and account identifier.

    Reserve quota before Argon2 work. Raise only AFTER the transaction commits,
    including the first throttled audit event in each bucket's time window.
    """
    limits = [(digest(action + ':ip:' + client), 30 if action == 'login' else 8)]
    if email:
        limits.append((digest(action + ':account:' + email), 8))
    current = int(time.time())
    retry_after = 0
    with connect_database(path, SCHEMA) as db:
        db.execute('BEGIN IMMEDIATE')
        cleanup(db)
        for bucket, maximum in limits:
            row = db.execute('SELECT * FROM auth_limits WHERE bucket=?', (bucket,)).fetchone()
            if row and row['attempts'] >= maximum:
                retry_after = max(retry_after, row['started_at']+WINDOW_SECONDS-current)
                if not row['reported']:
                    record(db, 'AUTH_THROTTLED', email=email, client=client)
                    db.execute('UPDATE auth_limits SET reported=1 WHERE bucket=?', (bucket,))
        # Count IP requests even when the account limit has already been hit.
        # Counters saturate; a rejected request never extends the original window.
        for bucket, maximum in limits:
            db.execute('''INSERT INTO auth_limits(bucket,started_at,attempts) VALUES(?,?,1)
                          ON CONFLICT(bucket) DO UPDATE SET attempts=MIN(attempts+1,?)''',
                       (bucket, current, maximum))
    if retry_after:
        raise HTTPException(429, 'Too many attempts. Try again later.',
                            headers={'Retry-After': str(max(1, math.ceil(retry_after)))})
