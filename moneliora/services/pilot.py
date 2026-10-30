"""Pilot request persistence, retention and operator workflow. No payment handling."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import uuid
from moneliora.database import connect_database
from moneliora.pagination import decode_pilot_cursor, pilot_cursor

STAGES = ('new', 'contacted', 'qualified', 'completed', 'declined')

@contextmanager
def connect(path):
    db = connect_database(path, '''CREATE TABLE IF NOT EXISTS pilot_requests (
        id TEXT PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL,
        offer TEXT NOT NULL, objective TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'new',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, consent_version TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS pilot_email_offer ON pilot_requests(email, offer);
        CREATE INDEX IF NOT EXISTS pilot_page ON pilot_requests(created_at DESC,id DESC);''')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def now():
    return datetime.now(timezone.utc)


def prune(db, instant):
    cutoff = (instant - timedelta(days=30)).isoformat()
    return db.execute('DELETE FROM pilot_requests WHERE created_at < ?', (cutoff,)).rowcount


def create(path, data):
    instant = now()
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        prune(db, instant)
        existing = db.execute('SELECT id FROM pilot_requests WHERE email=? AND offer=? AND created_at>=?',
                              (str(data.email).lower(), data.offer, (instant-timedelta(days=1)).isoformat())).fetchone()
        if existing:
            return
        db.execute('''INSERT INTO pilot_requests(id,email,name,offer,objective,created_at,updated_at,consent_version)
                      VALUES(?,?,?,?,?,?,?,?)''', (uuid.uuid4().hex, str(data.email).lower(), data.name,
                      data.offer, data.objective, instant.isoformat(), instant.isoformat(), 'pilot-v1'))


def listing(path, limit=100, cursor=None):
    position = decode_pilot_cursor(cursor) if cursor else None
    with connect(path) as db:
        prune(db, now())
        where = 'WHERE (created_at,id)<(?,?)' if position else ''
        rows = db.execute('SELECT * FROM pilot_requests '+where+' ORDER BY created_at DESC,id DESC LIMIT ?',
                          (*position,limit+1) if position else (limit+1,)).fetchall()
        more = len(rows)>limit
        rows = rows[:limit]
        counts = {stage: 0 for stage in STAGES}
        for row in db.execute('SELECT stage, COUNT(*) AS count FROM pilot_requests GROUP BY stage'):
            counts[row['stage']] = row['count']
        return {'requests': [dict(row) for row in rows], 'counts': counts, 'retention_days': 30,
                'has_more':more, 'next_cursor':pilot_cursor(rows[-1]) if more else None, 'limit':limit}


def transition(path, request_id, stage):
    with connect(path) as db:
        return db.execute('UPDATE pilot_requests SET stage=?,updated_at=? WHERE id=?',
                          (stage, now().isoformat(), request_id)).rowcount > 0


def remove(path, request_id):
    with connect(path) as db:
        return db.execute('DELETE FROM pilot_requests WHERE id=?', (request_id,)).rowcount > 0
