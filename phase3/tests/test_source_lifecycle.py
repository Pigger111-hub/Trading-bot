"""Synthetic lifecycle only; fixtures explicitly isolated in Hermes scratch."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import pytest
from lab3 import sources
from lab3.store import Store, digest


@pytest.fixture
def synthetic_store():
    scratch = Path('C:/Users/STANDARD_DOH/AppData/Local/hermes/cache/scratch')
    root = Path(tempfile.mkdtemp(prefix='synthetic-source-lifecycle-', dir=scratch))
    try:
        store = Store(root)
        store.put('sources', {'id': 'synthetic-doi', 'doi': '10.1234/synthetic',
                  'title': 'Synthetic Registered Title', 'status': sources.PENDING,
                  'approved': False, 'evidence_scope': 'CROSSREF_METADATA_ONLY'})
        yield store
    finally:
        shutil.rmtree(root)


class SyntheticFetcher:
    raw = ('<html><main>Synthetic Registered Title 10.1234/synthetic ' +
           'Synthetic mechanics evidence. ' * 20 + '</main></html>').encode()
    def __init__(self):
        self.calls = []
    def get(self, url, allowed):
        self.calls.append((url, allowed))
        return {'raw': self.raw, 'final_url': url, 'content_type': 'text/html'}


def verify(store, fetcher=None, **kwargs):
    return sources.verify_source(store, 'synthetic-doi', url='https://example.org/synthetic',
                                 actor='human', reviewer='Synthetic reviewer', reason='Synthetic association inspection',
                                 fetcher=fetcher or SyntheticFetcher(), **kwargs)


def test_manual_quarantine_approval_and_frozen_selection(synthetic_store):
    store = synthetic_store
    fetcher = SyntheticFetcher()
    quarantined = verify(store, fetcher)
    assert quarantined['status'] == 'QUARANTINED_DOCUMENT_TEXT'
    assert quarantined['approved'] is False
    assert quarantined['association']['heuristic_not_scientific_proof'] is True
    assert quarantined['raw_sha256'] == hashlib.sha256(fetcher.raw).hexdigest()
    assert sources.select_frozen_documents(store) == []
    approved = sources.approve_source(store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                                      reason='Synthetic full document inspected', scope='full-document')
    assert approved['status'] == 'APPROVED_REVIEWED_DOCUMENT'
    assert approved['approval']['quarantine_item_hash'] == digest(quarantined)
    assert approved['approval']['source_version'] == approved['version']
    selected = sources.select_frozen_documents(store)
    assert selected == [approved]
    assert len(fetcher.calls) == 1
    assert len(store.events('item_saved')) == 3


def test_subsequent_synthetic_cycle_uses_frozen_document_preserves_rediscovery_and_citations(synthetic_store, monkeypatch):
    from lab3 import research
    from test_research import synthetic_draft
    store = synthetic_store
    verify(store)
    approved = sources.approve_source(store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                                      reason='Synthetic full document inspected', scope='full-document')
    monkeypatch.setattr(research, 'verify_baseline', lambda _: {'verified': True, 'synthetic': True})
    monkeypatch.setattr(research, 'load_prior', lambda _: {'scope': 'Synthetic prior only'})
    monkeypatch.setattr(research, 'reviewed_seeds', lambda _: ['https://example.org/seed1', 'https://example.org/seed2'])
    monkeypatch.setattr(research.planning, 'exposed_windows', lambda _: [{'start': '2024-01-01T00:00:00Z', 'end': '2026-10-01T00:00:00Z'}])
    # This ID deliberately matches the frozen source to reproduce Crossref rediscovery.
    monkeypatch.setattr(research, 'discover', lambda *_: [{'id': 'synthetic-doi', 'doi': '10.1234/synthetic',
        'title': 'Synthetic refreshed metadata', 'status': sources.PENDING, 'approved': False,
        'evidence_scope': 'CROSSREF_METADATA_ONLY', 'verification': {'synthetic': True}}])
    class SyntheticModel:
        def complete(self, role, prompt):
            if role == 'research_planner':
                return {'questions_th': ['คำถามสังเคราะห์'], 'queries': {f: f for f in sources.FAMILIES}}
            if role == 'knowledge_researcher':
                assert 'Synthetic mechanics evidence' in prompt
                draft = synthetic_draft()
                draft['cards'][0]['quotes'][0]['source_id'] = 'synthetic-doi'
                for h in draft['hypotheses']:
                    h['source_ids'] = ['synthetic-doi']
                return draft
            return {'verdict': 'ACCEPT_AS_PROPOSAL', 'issues': [], 'lessons_th': [], 'next_questions': []}
    fetcher = SyntheticFetcher()
    research.run_cycle(store.root, model=SyntheticModel(), fetcher=fetcher)
    current = next(s for s in store.snapshot()['sources'] if s['id'] == 'synthetic-doi')
    assert current == approved
    assert [url for url, _ in fetcher.calls] == ['https://example.org/seed1']
    citation = store.snapshot()['cards'][0]['quotes'][0]
    assert citation == {'source_id': approved['id'], 'quote': 'Synthetic mechanics evidence',
                        'source_version': approved['version'], 'source_item_hash': digest(approved),
                        'raw_sha256': approved['raw_sha256'], 'text_sha256': approved['text_sha256']}
    changed = SyntheticFetcher()
    changed.raw = changed.raw.replace(b'Synthetic mechanics evidence', b'Revised synthetic document')
    verify(store, changed)
    assert sources.select_frozen_documents(store) == []
    assert store.snapshot()['cards'][0]['quotes'][0] == citation


def test_verify_baseline_delegates_canonical_helper(monkeypatch):
    from lab3 import research
    expected = {'verified': True, 'file_count': 56, 'manifest_sha256': 'synthetic-canonical'}
    monkeypatch.setattr(research.planning, 'verify_original_baseline', lambda root: expected, raising=False)
    assert research.verify_baseline(Path('synthetic-unused-root')) == expected


def test_human_cli_verify_and_full_document_scope(synthetic_store, monkeypatch, capsys):
    import json
    from lab3.cli import main
    monkeypatch.setattr(sources, 'SafeFetcher', SyntheticFetcher)
    argv = ['--root', str(synthetic_store.root)]
    assert main([*argv, 'verify-source', 'synthetic-doi', '--url', 'https://example.org/synthetic',
                 '--reviewer', 'Synthetic reviewer', '--reason', 'Synthetic inspection',
                 '--redirect-url', 'https://example.org/explicit-final']) == 0
    assert json.loads(capsys.readouterr().out)['approved'] is False
    assert main([*argv, 'approve-source', 'synthetic-doi', '--scope', 'full-document',
                 '--reviewer', 'Synthetic reviewer', '--reason', 'Synthetic full document review']) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'APPROVED_REVIEWED_DOCUMENT'


@pytest.mark.parametrize('raw', [b'', b'%PDF-1.7 synthetic',
    b'<html>captcha 10.1234/synthetic ' + b'blocked synthetic ' * 30 + b'</html>',
    b'<html>' + b'Unrelated synthetic document ' * 30 + b'</html>'])
def test_bad_documents_retain_rejected_history(synthetic_store, raw):
    fetcher = SyntheticFetcher()
    fetcher.raw = raw
    with pytest.raises(ValueError):
        verify(synthetic_store, fetcher)
    assert synthetic_store.snapshot()['sources'][0]['status'] == sources.PENDING
    assert len(synthetic_store.events('source_verification_rejected')) == 1
    received = synthetic_store.events('source_document_received')
    assert len(received) == 1
    assert received[0]['payload']['raw_sha256'] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize('mutation', ['text', 'raw', 'actor', 'version', 'metadata-only'])
def test_tampered_and_nonhuman_approvals_never_activate(synthetic_store, mutation):
    verify(synthetic_store)
    item = sources.approve_source(synthetic_store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                                  reason='Synthetic full document inspected', scope='full-document')
    if mutation == 'text':
        item['text'] += 'tampering'
    elif mutation == 'raw':
        item['raw_sha256'] = '0' * 64
    elif mutation == 'actor':
        item['approval']['actor'] = 'model'
    elif mutation == 'version':
        item['title'] += ' revised'
    else:
        item['status'] = 'APPROVED_METADATA_ONLY'
        item['evidence_scope'] = 'METADATA_REVIEW_ONLY'
    synthetic_store.put('sources', item)
    if mutation == 'metadata-only':
        assert sources.select_frozen_documents(synthetic_store) == []
    else:
        with pytest.raises(ValueError):
            sources.select_frozen_documents(synthetic_store)


def test_approval_rejects_modified_quarantine_and_retains_rejection(synthetic_store):
    item = verify(synthetic_store)
    # Rehashing a newly revised text cannot turn it into a verified snapshot.
    item['text'] += ' Synthetic tamper'
    item['text_sha256'] = hashlib.sha256(item['text'].encode()).hexdigest()
    synthetic_store.put('sources', item)
    with pytest.raises(ValueError, match='verified quarantine'):
        sources.approve_source(synthetic_store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                               reason='Synthetic full document inspected', scope='full-document')
    assert len(synthetic_store.events('source_approval_rejected')) == 1


def test_rebinding_modified_approval_is_not_a_human_review(synthetic_store):
    verify(synthetic_store)
    approved = sources.approve_source(synthetic_store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                                      reason='Synthetic reviewed', scope='full-document')
    approved['approval']['reason'] = 'Synthetic fabricated replacement reason'
    approved['approval']['source_version'] += 1
    synthetic_store.put('sources', approved)
    with pytest.raises(ValueError, match='approval receipt'):
        sources.select_frozen_documents(synthetic_store)


def test_unsupported_response_content_type_is_not_document_evidence(synthetic_store):
    class SyntheticJSON(SyntheticFetcher):
        def get(self, url, allowed):
            return {**super().get(url, allowed), 'content_type': 'application/json'}
    with pytest.raises(ValueError, match='content type'):
        verify(synthetic_store, SyntheticJSON())


def test_nonhuman_verification_is_rejected_before_network_and_audited(synthetic_store):
    fetcher = SyntheticFetcher()
    with pytest.raises(ValueError, match='human'):
        sources.verify_source(synthetic_store, 'synthetic-doi', url='https://example.org/synthetic',
                              actor='model', reviewer='Synthetic model', reason='Synthetic denied', fetcher=fetcher)
    assert fetcher.calls == []
    assert len(synthetic_store.events('source_verification_rejected')) == 1


@pytest.mark.parametrize('scope', ['metadata-only', 'full-document'])
def test_pending_or_metadata_only_is_never_full_document_activation(synthetic_store, scope):
    store = synthetic_store
    if scope == 'metadata-only':
        sources.approve_source(store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                               reason='Synthetic metadata inspection')
    with pytest.raises(ValueError, match='quarantined'):
        sources.approve_source(store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                               reason='Synthetic denied activation', scope='full-document')
    assert sources.select_frozen_documents(store) == []


def test_selection_never_exceeds_two_reviewed_frozen_documents(synthetic_store):
    store = synthetic_store
    verify(store)
    sources.approve_source(store, 'synthetic-doi', actor='human', reviewer='Synthetic reviewer',
                           reason='Synthetic review', scope='full-document')
    for index in range(2):
        source_id = f'synthetic-extra-{index}'
        store.put('sources', {'id': source_id, 'doi': '10.1234/synthetic',
                  'title': 'Synthetic Registered Title', 'status': sources.PENDING, 'approved': False})
        sources.verify_source(store, source_id, url=f'https://example.org/synthetic-{index}',
                              actor='human', reviewer='Synthetic reviewer', reason='Synthetic inspection',
                              fetcher=SyntheticFetcher())
        sources.approve_source(store, source_id, actor='human', reviewer='Synthetic reviewer',
                               reason='Synthetic review', scope='full-document')
    assert len(sources.select_frozen_documents(store)) == 2


@pytest.mark.parametrize('raw, doi_match, title_match', [
    (b'Synthetic Registered Title ' + b'Synthetic document. ' * 30, False, True),
    (b'10.1234/synthetic ' + b'Synthetic document. ' * 30, True, False)])
def test_association_accepts_doi_or_registered_title_but_remains_heuristic(synthetic_store, raw, doi_match, title_match):
    fetcher = SyntheticFetcher()
    fetcher.raw = raw
    verified = verify(synthetic_store, fetcher)
    assert verified['association'] == {'doi_match': doi_match, 'registered_title_match': title_match,
                                       'heuristic_not_scientific_proof': True}
    assert verified['approved'] is False
