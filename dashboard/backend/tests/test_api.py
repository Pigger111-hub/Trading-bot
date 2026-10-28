"""API behavior tests use an explicitly SYNTHETIC store, not research evidence."""
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


class SyntheticStore:
    def overview(self):
        return {'batch_id': 'SYNTHETIC_TEST', 'simulation': True, 'integrity': {'verified': True}}


@pytest.fixture
def client(tmp_path):
    from dashboard_api.app import create_app
    return TestClient(create_app(root=tmp_path, store=SyntheticStore()), base_url='http://127.0.0.1:8765')


def test_overview_is_explicitly_read_only_and_has_no_cache(client):
    response = client.get('/api/overview')
    assert response.status_code == 200
    assert response.json()['batch_id'] == 'SYNTHETIC_TEST'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_head_is_a_read_only_equivalent_of_get(client):
    response = client.head('/api/overview')
    assert response.status_code == 200
    assert response.content == b''


def test_invalid_origin_fails_closed_without_server_error(client):
    assert client.get('/api/overview', headers={'Origin': 'http://['}).status_code == 403


def test_no_mutating_routes_or_research_execution(client):
    for method in ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']:
        for path in ['/api/overview', '/api/experiment', '/api/approve', '/api/research', '/']:
            assert client.request(method, path).status_code == 405


def test_non_loopback_host_or_foreign_origin_cannot_read(client):
    assert client.get('/api/overview', headers={'Host': 'evil.example'}).status_code == 400
    assert client.get('/api/overview', headers={'Origin': 'https://evil.example'}).status_code == 403


def test_no_generic_filesystem_endpoint_or_encoded_traversal(client):
    for path in ['/api/files?path=storage/lab.sqlite', '/storage/lab.sqlite', '/api/../../storage/lab.sqlite']:
        assert client.get(path).status_code == 404


def test_integrity_error_never_returns_a_verified_snapshot(tmp_path):
    from dashboard_api.app import create_app
    class CorruptSyntheticStore:
        def overview(self):
            raise ValueError('SYNTHETIC integrity failure at a private path')
    c = TestClient(create_app(root=tmp_path, store=CorruptSyntheticStore()), base_url='http://localhost:8765')
    response = c.get('/api/overview')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'INTEGRITY_ERROR'
    assert 'private path' not in response.text


def test_app_requests_do_not_create_files(client):
    root = Path(client.app.state.root)
    before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
    client.get('/api/overview')
    assert sorted(str(p.relative_to(root)) for p in root.rglob('*')) == before
