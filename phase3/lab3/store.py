"""Standalone stdlib append-only research evidence store; no controller imports."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

COLLECTIONS = ('sources', 'cards', 'gaps', 'hypotheses', 'queue', 'lessons', 'cycles')
SAFETY = dict(execution_enabled=False, scheduler_enabled=False, credentials_enabled=False)


class IntegrityError(ValueError):
    """Persisted evidence cannot be trusted."""


def canonical(value):
    def check(node):
        if isinstance(node, dict):
            if any(not isinstance(key, str) for key in node):
                raise ValueError('JSON object keys must be strings')
            for child in node.values():
                check(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                check(child)
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _empty() -> dict:
    return dict(available=False, integrity=dict(verified=False, event_count=0, head_hash=None),
                **{k: [] for k in COLLECTIONS}, safety=dict(SAFETY), counts={k: 0 for k in COLLECTIONS})


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / 'phase3' / 'state' / 'lab.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
                prev_hash TEXT, hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT,'append only'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT,'append only'); END;''')
            db.commit()

    @contextmanager
    def _write(self):
        with closing(sqlite3.connect(self.path, timeout=30)) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                self._events(db)
                yield db
                self._project(self._events(db))
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _events(db):
        try:
            rows = db.execute('SELECT id,kind,payload,prev_hash,hash,created_at FROM events ORDER BY rowid').fetchall()
            result, prev = [], None
            for row in rows:
                event = dict(zip(('id','kind','payload','prev_hash','hash','created_at'), row))
                event['payload'] = json.loads(event['payload'], parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                hashed = {k: v for k, v in event.items() if k != 'hash'}
                if event['prev_hash'] != prev or digest(hashed) != event['hash']:
                    raise IntegrityError('Event chain mismatch')
                if not isinstance(event['payload'], dict):
                    raise IntegrityError('Invalid payload')
                result.append(event)
                prev = event['hash']
            return result
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise IntegrityError(str(exc)) from exc

    @staticmethod
    def _append(db, kind, payload):
        if not isinstance(kind, str) or not kind.strip() or not isinstance(payload, dict):
            raise ValueError('Nonblank kind and dict payload required')
        payload = json.loads(canonical(payload))
        row = db.execute('SELECT hash FROM events ORDER BY rowid DESC LIMIT 1').fetchone()
        event = dict(id=str(uuid.uuid4()), kind=kind, payload=payload, prev_hash=row[0] if row else None,
                     created_at=datetime.now(timezone.utc).isoformat())
        event['hash'] = digest(event)
        db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                   (event['id'], kind, canonical(payload), event['prev_hash'], event['hash'], event['created_at']))
        return event

    def append(self, kind, payload):
        with self._write() as db:
            return self._append(db, kind, payload)

    def events(self, kind=None):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('BEGIN')
            return [e for e in self._events(db) if kind is None or e['kind'] == kind]

    @staticmethod
    def _project(events):
        snap = _empty()
        snap['available'] = True
        snap['integrity'] = dict(verified=True, event_count=len(events), head_hash=events[-1]['hash'] if events else None)
        latest = {k: {} for k in COLLECTIONS}
        for event in events:
            if event['kind'] != 'item_saved':
                continue
            try:
                payload = event['payload']
                collection, item = payload['collection'], payload['item']
                if collection not in COLLECTIONS or not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip():
                    raise ValueError('Invalid item_saved schema')
                prior = latest[collection].get(item['id'])
                if type(item.get('version')) is not int or item['version'] != (prior['version'] + 1 if prior else 1):
                    raise ValueError('Invalid revision sequence')
                if item.get('previous_version_hash') != (digest(prior) if prior else None):
                    raise ValueError('Invalid revision predecessor')
                latest[collection][item['id']] = item
            except (KeyError, TypeError, ValueError) as exc:
                raise IntegrityError(str(exc)) from exc
        for collection in COLLECTIONS:
            snap[collection] = list(latest[collection].values())
            snap['counts'][collection] = len(snap[collection])
        return snap

    @classmethod
    def _put(cls, db, collection, item):
        if collection not in COLLECTIONS or not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip():
            raise ValueError('Valid collection and nonblank item id required')
        clean = json.loads(canonical(item))
        clean.pop('version', None)
        clean.pop('previous_version_hash', None)
        prior = next((i for i in cls._project(cls._events(db))[collection] if i['id'] == clean['id']), None)
        if prior:
            old = {k: v for k, v in prior.items() if k not in ('version', 'previous_version_hash')}
            if old == clean:
                raise ValueError('Identical duplicate revision')
        clean.update(version=prior['version'] + 1 if prior else 1,
                     previous_version_hash=digest(prior) if prior else None)
        cls._append(db, 'item_saved', dict(collection=collection, item=clean))
        return clean

    def put(self, collection, item):
        with self._write() as db:
            return self._put(db, collection, item)

    def start_cycle(self):
        with self._write() as db:
            cycles = self._project(self._events(db))['cycles']
            if any(c.get('status') == 'RUNNING' for c in cycles):
                raise ValueError('Active cycle exists; explicit recovery required')
            return self._put(db, 'cycles', dict(id=str(uuid.uuid4()), status='RUNNING'))

    def _active(self, db, cycle_id):
        active = [c for c in self._project(self._events(db))['cycles'] if c.get('status') == 'RUNNING']
        if len(active) != 1 or active[0]['id'] != cycle_id:
            raise ValueError('Cycle is not active')
        return active[0]

    def reserve_model_call(self, cycle_id, role, cap=3):
        if type(cap) is not int or not 1 <= cap <= 3:
            raise ValueError('Cap must be integer 1..3')
        if role not in ('research_planner', 'knowledge_researcher', 'independent_critic'):
            raise ValueError('Unknown model role')
        with self._write() as db:
            self._active(db, cycle_id)
            used = sum(e['kind'] == 'model_call_reserved' and e['payload'].get('cycle_id') == cycle_id
                       for e in self._events(db))
            if used >= cap:
                raise ValueError('Model call cap exhausted')
            return self._append(db, 'model_call_reserved', dict(cycle_id=cycle_id, role=role, ordinal=used + 1))

    def finish_cycle(self, cycle_id, status, details):
        if status not in ('COMPLETED', 'FAILED', 'INTERRUPTED') or not isinstance(details, dict):
            raise ValueError('Invalid cycle completion')
        with self._write() as db:
            cycle = self._active(db, cycle_id)
            return self._put(db, 'cycles', dict(cycle, status=status, details=details))

    def snapshot(self):
        return self.read_snapshot(self.root)

    @staticmethod
    def read_snapshot(root):
        path = Path(root).resolve() / 'phase3' / 'state' / 'lab.sqlite'
        if not path.exists():
            return _empty()
        try:
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                db.execute('PRAGMA query_only=ON')
                db.execute('BEGIN')
                return Store._project(Store._events(db))
        except sqlite3.Error as exc:
            raise IntegrityError(str(exc)) from exc
