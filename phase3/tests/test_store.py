"""Store tests use synthetic scratch-only evidence."""
import importlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import pytest


def api():
    return importlib.import_module('lab3.store')


def test_synthetic_append_chain_and_read_only_absence(tmp_path):
    m = api()
    assert hasattr(m, 'Store'), 'Store public interface missing'
    absent = m.Store.read_snapshot(tmp_path)
    assert not absent['available']
    assert not (tmp_path / 'phase3').exists()
    store = m.Store(tmp_path)
    a = store.append('synthetic', {'text': 'ไทย'})
    b = store.append('synthetic', {'n': 2})
    assert b['prev_hash'] == a['hash']
    assert store.events() == [a, b]
    snap = m.Store.read_snapshot(tmp_path)
    assert snap['integrity'] == {'verified': True, 'event_count': 2, 'head_hash': b['hash']}
    assert not any(snap['safety'].values())
    with pytest.raises(ValueError):
        store.append('synthetic', {'n': float('nan')})


@pytest.mark.parametrize('payload',[{'x':float('inf')},{'x':float('-inf')},{1:'non-string-key'},{'nested':{False:'bad'}}])
def test_synthetic_strict_json_rejected_without_reservation(tmp_path,payload):
    store = api().Store(tmp_path)
    with pytest.raises(ValueError):
        store.append('synthetic',payload)
    assert store.events() == []


def test_synthetic_read_snapshot_corruption_never_creates_files(tmp_path):
    m = api()
    state = tmp_path/'phase3/state'
    state.mkdir(parents=True)
    db = state/'lab.sqlite'
    db.write_bytes(b'SYNTHETIC corrupt not SQLite')
    before = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in state.iterdir()}
    with pytest.raises(m.IntegrityError):
        m.Store.read_snapshot(tmp_path)
    assert before == {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in state.iterdir()}


def test_synthetic_invalid_revision_event_rolls_back(tmp_path):
    store = api().Store(tmp_path)
    with pytest.raises(ValueError):
        store.append('item_saved',dict(collection='cards',item=dict(id='synthetic-forged',version=99,previous_version_hash=None)))
    assert store.events() == []
    assert store.snapshot()['integrity']['verified']


def test_synthetic_valid_read_snapshot_does_not_touch_files(tmp_path):
    m = api()
    store = m.Store(tmp_path)
    store.put('sources',{'id':'synthetic-source','untrusted_extra':'<script>data only</script>'})
    state = store.path.parent
    before = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in state.iterdir()}
    for _ in range(3):
        snap = m.Store.read_snapshot(tmp_path)
        assert snap['sources'][0]['untrusted_extra'] == '<script>data only</script>'
        assert not any(snap['safety'].values())
    assert before == {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in state.iterdir()}


def test_synthetic_atomic_cycle_reservations_and_recovery(tmp_path):
    m = api()
    store = m.Store(tmp_path)
    def start(_):
        try:
            return store.start_cycle()
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        starts = [x for x in pool.map(start, range(4)) if x]
    assert len(starts) == 1
    cycle = starts[0]
    for cap in (True, 1.5, 0, 4):
        with pytest.raises(ValueError):
            store.reserve_model_call(cycle['id'], 'research_planner', cap)
    def reserve(_):
        try:
            return store.reserve_model_call(cycle['id'], 'research_planner')
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        reservations = [x for x in pool.map(reserve, range(6)) if x]
    assert len(reservations) == 3
    with pytest.raises(ValueError):
        store.finish_cycle('not-active', 'COMPLETED', {})
    store.finish_cycle(cycle['id'], 'INTERRUPTED', {'reason': 'synthetic explicit recovery'})
    with pytest.raises(ValueError):
        store.reserve_model_call(cycle['id'], 'knowledge_researcher')
    assert store.start_cycle()['id'] != cycle['id']


def test_synthetic_immutable_revisions_and_tamper(tmp_path):
    m = api()
    store = m.Store(tmp_path)
    first = store.put('cards', {'id': 'synthetic-card', 'text': 'one'})
    second = store.put('cards', {'id': 'synthetic-card', 'text': 'two'})
    assert first['version'] == 1 and second['version'] == 2
    assert second['previous_version_hash'] == m.digest(first)
    assert store.snapshot()['cards'] == [second]
    with pytest.raises(ValueError):
        store.put('cards', {'id': 'synthetic-card', 'text': 'two'})
    with pytest.raises(ValueError):
        store.put('unknown', {'id': 'x'})
    with closing(sqlite3.connect(store.path)) as db, db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE events SET kind='tampered'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('DELETE FROM events')
        db.execute('DROP TRIGGER events_no_update')
        db.execute("UPDATE events SET kind='tampered'")
    with pytest.raises(m.IntegrityError):
        m.Store.read_snapshot(tmp_path)
    with pytest.raises(m.IntegrityError):
        store.events('irrelevant-filter-still-verifies-all-events')
