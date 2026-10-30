"""SQLite connections with bounded lock waits, WAL and deterministic cleanup."""
from pathlib import Path
import sqlite3


class Connection(sqlite3.Connection):
    def __exit__(self, *exc):
        try:
            return super().__exit__(*exc)
        finally:
            self.close()


def connect_database(path, schema=''):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, factory=Connection)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('PRAGMA foreign_keys=ON')
        if db.execute('PRAGMA journal_mode').fetchone()[0].lower() != 'wal':
            db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        if schema:
            db.executescript(schema)
        return db
    except BaseException:
        db.close()
        raise
