"""Phase3 read-only integration; all new state fixtures are SYNTHETIC scratch data."""
from pathlib import Path
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]


class SyntheticEvidence:
    def overview(self):
        return {'integrity': {'verified': True}}


def client(root, store=None):
    from dashboard_api.app import create_app
    return TestClient(create_app(root=root, store=store or SyntheticEvidence()),
                      base_url='http://127.0.0.1:8765')


def test_missing_phase3_returns_empty_without_creating_state(tmp_path):
    before = list(tmp_path.rglob('*'))
    response = client(tmp_path).get('/api/phase3')
    assert response.status_code == 200
    body = response.json()
    assert body['available'] is False
    assert body['integrity'] == {'verified': False, 'event_count': 0, 'head_hash': None}
    for name in ('sources', 'cards', 'gaps', 'hypotheses', 'queue', 'lessons', 'cycles'):
        assert body[name] == [] and body['counts'][name] == 0
    assert list(tmp_path.rglob('*')) == before
    assert response.headers['cache-control'] == 'no-store'


def test_unverified_original_cannot_present_phase3(tmp_path):
    class UnverifiedEvidence:
        def overview(self):
            return {'integrity': {'verified': False}}
    assert client(tmp_path, UnverifiedEvidence()).get('/api/phase3').status_code == 503


def inventory(root):
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns,
            hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob('*') if p.is_file()}


def test_versioned_phase3_snapshot_head_and_all_read_only_boundaries(tmp_path):
    from lab3.store import Store
    store = Store(tmp_path)
    store.put('cards', {'id': 'SYNTHETIC card', 'claim': '<script>untrusted</script>'})
    revised = store.put('cards', {'id': 'SYNTHETIC card', 'claim': 'SYNTHETIC revision'})
    store.put('queue', {'id': 'SYNTHETIC proposal', 'status': 'PROPOSED', 'engine_evaluations_consumed': 0})
    before = inventory(tmp_path)
    c = client(tmp_path)
    response = c.get('/api/phase3')
    assert response.status_code == 200
    assert response.json() == Store.read_snapshot(tmp_path)
    assert response.json()['cards'] == [revised]
    assert response.json()['counts']['cards'] == 1
    assert response.json()['queue'][0]['status'] == 'PROPOSED'
    assert all(flag is False for flag in response.json()['safety'].values())
    assert c.head('/api/phase3').status_code == 200
    assert c.head('/api/phase3').content == b''
    assert "connect-src 'self'" in response.headers['content-security-policy']
    assert c.get('/api/phase3', headers={'Host': 'evil.example'}).status_code == 400
    assert c.get('/api/phase3', headers={'Origin': 'https://evil.example'}).status_code == 403
    for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'):
        assert c.request(method, '/api/phase3').status_code == 405
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('corruption', ['not_sqlite', 'changed_payload'])
def test_corrupt_phase3_fails_closed_without_writing_or_leaking_paths(tmp_path, corruption):
    from lab3.store import Store
    import sqlite3
    from contextlib import closing
    assert 'hermes/cache/scratch' in tmp_path.as_posix()
    store = Store(tmp_path)
    store.put('cards', {'id': 'SYNTHETIC corrupt copy', 'claim': 'test'})
    path = tmp_path / 'phase3/state/lab.sqlite'
    if corruption == 'not_sqlite':
        path.write_bytes(b'SYNTHETIC corrupt sqlite')
    else:
        with closing(sqlite3.connect(path)) as db:
            db.execute('DROP TRIGGER events_no_update')
            db.execute("UPDATE events SET payload='{}'")
            db.commit()
    before = inventory(tmp_path)
    response = client(tmp_path).get('/api/phase3')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'INTEGRITY_ERROR'
    assert str(tmp_path) not in response.text
    assert 'SYNTHETIC corrupt' not in response.text
    assert inventory(tmp_path) == before


def test_original_evidence_failure_prevents_even_reading_phase3(tmp_path, monkeypatch):
    from lab3.store import Store
    def forbidden(_root):
        pytest.fail('Phase3 must not be read after original evidence failure')
    monkeypatch.setattr(Store, 'read_snapshot', forbidden)
    class CorruptEvidence:
        def overview(self):
            raise ValueError('SYNTHETIC original corruption')
    response = client(tmp_path, CorruptEvidence()).get('/api/phase3')
    assert response.status_code == 503
    assert list(tmp_path.rglob('*')) == []


def test_actual_batch_validation_and_phase3_read_preserve_56_baseline_files():
    from dashboard_api.app import create_app
    baseline = json.loads((ROOT / 'dashboard/qa/baseline-evidence.json').read_text())
    def protected():
        return {name: (hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
                       (ROOT / name).stat().st_mtime_ns, (ROOT / name).stat().st_size) for name in baseline}
    before = protected()
    assert len(before) == 56
    assert {name: meta[0] for name, meta in before.items()} == baseline
    c = TestClient(create_app(root=ROOT), base_url='http://localhost:8765')
    response = c.get('/api/phase3')
    assert response.status_code == 200
    assert response.json()['safety']['execution_enabled'] is False
    assert c.get('/api/overview').json()['integrity']['engine_evaluations'] == 20
    assert protected() == before
