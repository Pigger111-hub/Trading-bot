"""Synthetic network fixtures only; no internet calls."""
import pytest
from lab3.sources import NetworkBudget, validate_url, discover, FAMILIES


def test_dns_resolution_has_an_explicit_deadline(monkeypatch):
    import time
    from lab3.sources import resolve_public
    def synthetic_blocked_dns(*args, **kwargs):
        time.sleep(0.05)
        return [(2, 1, 6, '', ('93.184.216.34', 443))]
    monkeypatch.setattr('socket.getaddrinfo', synthetic_blocked_dns)
    with pytest.raises(TimeoutError):
        resolve_public('example.org', timeout=0.001)


def test_fetch_rejects_private_dns_before_transport(monkeypatch):
    from lab3.sources import SafeFetcher
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='nonpublic'):
        SafeFetcher().get('https://example.org/doc', {'https://example.org/doc'})


def test_synthetic_transport_redirect_escape_and_size_budget(monkeypatch):
    import socket
    from lab3.sources import SafeFetcher
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('93.184.216.34', 443))])
    class SyntheticSocket:
        def close(self):
            pass
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: SyntheticSocket())
    class SyntheticTLS:
        def wrap_socket(self, sock, server_hostname):
            assert server_hostname == 'example.org'
            return sock
    monkeypatch.setattr('ssl.create_default_context', SyntheticTLS)
    class SyntheticResponse:
        status = 302
        def getheader(self, name, default=None):
            return 'https://127.0.0.1/private' if name == 'Location' else default
        def read(self, amount):
            return b'x' * amount
    response = SyntheticResponse()
    watchdogs = []
    class SyntheticWatchdog:
        def __init__(self, delay, callback):
            assert 0 < delay <= 35
            self.active = False
            watchdogs.append(self)
        def start(self):
            self.active = True
        def cancel(self):
            self.active = False
    monkeypatch.setattr('threading.Timer', SyntheticWatchdog)
    class SyntheticConnection:
        def __init__(self, *a, context=None, **k):
            self._context = context
        def request(self, *a, **k):
            assert watchdogs and watchdogs[-1].active
            assert 'Authorization' not in k['headers']
        def getresponse(self):
            return response
        def close(self):
            pass
    monkeypatch.setattr('http.client.HTTPSConnection', SyntheticConnection)
    fetcher = SafeFetcher()
    with pytest.raises(ValueError):
        fetcher.get('https://example.org/doc', {'https://example.org/doc'})
    assert fetcher.budget.requests == 1
    response.status = 200
    with pytest.raises(ValueError, match='1MB'):
        fetcher.get('https://example.org/doc', {'https://example.org/doc'})
    assert fetcher.budget.requests == 2
    response.read = lambda amount: b''
    ticks = iter([0, 100, 100, 100, 100])
    monkeypatch.setattr('time.monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError):
        fetcher.get('https://example.org/doc', {'https://example.org/doc'})


def test_reviewed_seed_catalog_hash_and_human_approval(tmp_path):
    from lab3.sources import reviewed_seeds, approve_source
    from lab3.store import Store
    with pytest.raises(ValueError):
        reviewed_seeds(tmp_path)
    store = Store(tmp_path)
    store.put('sources', {'id': 'synthetic-candidate', 'status': 'VERIFIED_METADATA_PENDING_HUMAN_APPROVAL', 'approved': False})
    with pytest.raises(ValueError):
        approve_source(store, 'synthetic-candidate', actor='model', reviewer='Synthetic', reason='Synthetic')
    with pytest.raises(ValueError):
        approve_source(store, 'synthetic-candidate', actor='human', reviewer='Synthetic', reason=' ')
    approved = approve_source(store, 'synthetic-candidate', actor='human', reviewer='Synthetic', reason='Synthetic metadata review only')
    assert approved['approved'] is True
    assert approved['evidence_scope'] == 'METADATA_REVIEW_ONLY'
    assert len(store.snapshot()['sources'][0]['review_history']) == 1


def test_exact_https_policy_and_hard_request_budget():
    allowed = {'https://example.org/doc'}
    assert validate_url('https://example.org/doc', allowed) == 'https://example.org/doc'
    for url in ['https://example.org/other', 'http://example.org/doc', 'https://u:p@example.org/doc', 'https://127.0.0.1/doc']:
        with pytest.raises(ValueError):
            validate_url(url, allowed)
    with pytest.raises(ValueError):
        validate_url('https://example.org:443/doc', {'https://example.org:443/doc'})
    budget = NetworkBudget()
    for _ in range(12):
        budget.consume()
    with pytest.raises(ValueError):
        budget.consume()


def test_four_family_crossref_candidates_remain_pending():
    calls = []
    def synthetic_get(url, allowed):
        calls.append(url)
        return {'raw': b'{"message":{"items":[{"DOI":"10.1234/synthetic","title":["Synthetic title"],"publisher":"Synthetic Publisher","type":"journal-article"}]}}', 'final_url': url}
    candidates = discover({family: 'synthetic ' + family for family in FAMILIES}, synthetic_get)
    assert len(calls) == 4
    assert len(candidates) == 1
    assert candidates[0]['status'] == 'VERIFIED_METADATA_PENDING_HUMAN_APPROVAL'
    assert candidates[0]['evidence_scope'] == 'CROSSREF_METADATA_ONLY'
    assert set(candidates[0]['families']) == set(FAMILIES)
