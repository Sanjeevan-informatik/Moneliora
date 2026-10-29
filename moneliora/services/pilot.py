"""Pilot request persistence, retention and operator workflow. No payment handling."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import sqlite3
import uuid

STAGES = ('new', 'contacted', 'qualified', 'completed', 'declined')

@contextmanager
def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('''CREATE TABLE IF NOT EXISTS pilot_requests (
        id TEXT PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL,
        offer TEXT NOT NULL, objective TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'new',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, consent_version TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS pilot_email_offer ON pilot_requests(email, offer)')
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


def listing(path):
    with connect(path) as db:
        prune(db, now())
        rows = db.execute('SELECT * FROM pilot_requests ORDER BY created_at DESC LIMIT 100').fetchall()
        counts = {stage: 0 for stage in STAGES}
        for row in db.execute('SELECT stage, COUNT(*) AS count FROM pilot_requests GROUP BY stage'):
            counts[row['stage']] = row['count']
        return {'requests': [dict(row) for row in rows], 'counts': counts, 'retention_days': 30}


def transition(path, request_id, stage):
    with connect(path) as db:
        return db.execute('UPDATE pilot_requests SET stage=?,updated_at=? WHERE id=?',
                          (stage, now().isoformat(), request_id)).rowcount > 0


def remove(path, request_id):
    with connect(path) as db:
        return db.execute('DELETE FROM pilot_requests WHERE id=?', (request_id,)).rowcount > 0
