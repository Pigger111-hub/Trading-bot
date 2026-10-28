"""Append-only, hash-chained audit events. Tamper-evident, not a same-user security boundary."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


class Registry:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
                    created TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL UNIQUE
                );
                CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT, 'append-only history'); END;
                CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT, 'append-only history'); END;
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def append(self, kind, payload):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return self.append_in(db, kind, payload)

    @staticmethod
    def append_in(db, kind, payload):
        if not isinstance(kind, str) or not kind:
            raise ValueError('event kind required')
        previous = db.execute('SELECT id, hash FROM events ORDER BY id DESC LIMIT 1').fetchone()
        number = previous['id'] + 1 if previous else 1
        chain = previous['hash'] if previous else '0' * 64
        created = datetime.now(timezone.utc).isoformat()
        encoded = canonical(payload)
        event_hash = digest([number, kind, encoded, created, chain])
        db.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)',
                   (number, kind, encoded, created, chain, event_hash))
        return event_hash

    def events(self, kind=None):
        with self.connect() as db:
            if kind is None:
                rows = db.execute('SELECT * FROM events ORDER BY id').fetchall()
            else:
                rows = db.execute('SELECT * FROM events WHERE kind=? ORDER BY id', (kind,)).fetchall()
        return [{**dict(row), 'payload': json.loads(row['payload'])} for row in rows]

    def verify(self):
        previous = '0' * 64
        with self.connect() as db:
            rows = db.execute('SELECT * FROM events ORDER BY id').fetchall()
        for number, row in enumerate(rows, 1):
            expected = digest([row['id'], row['kind'], row['payload'], row['created'], previous])
            if row['id'] != number or row['previous'] != previous or row['hash'] != expected:
                raise ValueError(f'audit chain invalid at event {number}')
            previous = row['hash']
        return len(rows)
