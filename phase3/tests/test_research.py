"""Synthetic research/model/network fixtures; no engine and no live provider."""
import pytest
from lab3.research import validate_research, validate_critic, SCORE_MEANING
from lab3.sources import FAMILIES


def synthetic_draft():
    return {'cards': [{'id': 'synthetic-card', 'title_th': 'การทดสอบสังเคราะห์',
                      'claim_th': 'ข้อจำกัดเชิงกลไก ไม่ใช่หลักฐานกำไร',
                      'uncertainties_th': ['ไม่ทราบ alpha'],
                      'quotes': [{'source_id': 'synthetic-seed', 'quote': 'Synthetic mechanics evidence'}]}],
            'hypotheses': [{'id': 'synthetic-' + family, 'family': family, 'title_th': 'สมมติฐาน',
                            'hypothesis_th': 'ต้องทดสอบก่อน', 'entry_logic': 'declarative threshold',
                            'exit_logic': 'declarative exit', 'falsification': 'Fails validation after costs',
                            'parameters': {'period': 20}, 'source_ids': ['synthetic-seed'],
                            'scores': {'evidence_quality': 2, 'novelty': 2, 'information_gain': 3, 'complexity': 2}}
                           for family in FAMILIES],
            'gaps_th': ['ข้อมูลอนาคตยังไม่ตรวจสอบ'], 'lessons_th': ['เอกสารไม่พิสูจน์กำไร'],
            'method_proposals_th': ['ตรวจสอบต้นทุนและอคติ']}


def test_literal_quote_quality_gate_and_four_family_schema():
    sources = [{'id': 'synthetic-seed', 'approved': True, 'evidence_scope': 'RETRIEVED_DOCUMENT_TEXT',
                'support_scope': 'MECHANICS_VALIDATION_ONLY', 'text': 'Synthetic mechanics evidence only.'},
               {'id': 'synthetic-doi', 'approved': False, 'evidence_scope': 'CROSSREF_METADATA_ONLY'}]
    assert validate_research(synthetic_draft(), sources)
    bad = synthetic_draft()
    bad['hypotheses'][0]['scores']['evidence_quality'] = 5
    with pytest.raises(ValueError, match='evidence_quality'):
        validate_research(bad, sources)
    bad = synthetic_draft()
    bad['cards'][0]['quotes'][0]['quote'] = 'invented exact quote'
    with pytest.raises(ValueError, match='literal'):
        validate_research(bad, sources)
    bad = synthetic_draft()
    bad['cards'][0]['quotes'][0]['source_id'] = 'synthetic-doi'
    with pytest.raises(ValueError):
        validate_research(bad, sources)
    assert 'recorded lab history' in SCORE_MEANING and 'ordinal' in SCORE_MEANING


@pytest.mark.parametrize('large_context', [False, True])
@pytest.mark.parametrize('verdict', ['ACCEPT_AS_PROPOSAL', 'REJECT', 'REVISE', 'INVALID_DRAFT'])
def test_one_synthetic_cycle_real_store_plans_and_preserved_rejections(tmp_path, monkeypatch, verdict, large_context):
    import json
    import lab3.research as research
    from lab3.store import Store
    monkeypatch.setattr(research, 'verify_baseline', lambda root: {'verified': True, 'synthetic': True})
    monkeypatch.setattr(research, 'load_prior', lambda root: {'scope': 'SYNTHETIC Batch001 prior', 'lessons_th': ['ข้อจำกัดเดิม'],
                                                           'synthetic_padding': 'x' * (12000 if large_context else 0)})
    if large_context:
        for collection in ('cards', 'gaps', 'hypotheses', 'lessons'):
            for index in range(6):
                Store(tmp_path).put(collection, {'id': f'synthetic-prior-{collection}-{index}', 'text': 'x' * 2000})
    monkeypatch.setattr(research, 'reviewed_seeds', lambda root: ['https://example.org/synthetic-1', 'https://example.org/synthetic-2'])
    monkeypatch.setattr(research.planning, 'exposed_windows', lambda root: [{'start': '2024-01-01T00:00:00Z', 'end': '2026-10-01T00:00:00Z'}])
    prompts = []
    class SyntheticModel:
        def complete(self, role, prompt):
            prompts.append((role, prompt))
            if role == 'research_planner':
                return {'questions_th': ['ศึกษาข้อจำกัดจากบทเรียนเดิม'], 'queries': {f: 'synthetic ' + f for f in FAMILIES}}
            if role == 'knowledge_researcher':
                draft = synthetic_draft()
                source_id = research.seed_id('https://example.org/synthetic-1')
                for h in draft['hypotheses']:
                    h['source_ids'] = [source_id]
                draft['cards'][0]['quotes'][0]['source_id'] = source_id
                if verdict == 'INVALID_DRAFT':
                    draft['cards'][0]['quotes'][0]['quote'] = 'Synthetic invented quotation absent from document'
                return draft
            return {'verdict': verdict, 'issues': [] if verdict == 'ACCEPT_AS_PROPOSAL' else ['Synthetic unsupported claim'],
                    'lessons_th': ['บทเรียนวิจารณ์'], 'next_questions': ['คำถามถัดไป']}
    class SyntheticNetwork:
        def get(self, url, allowed):
            assert url in allowed
            if 'api.crossref.org' in url:
                raw = json.dumps({'message': {'items': [{'DOI': '10.1234/synthetic', 'title': ['Synthetic metadata'],
                                                       'publisher': 'Synthetic', 'type': 'journal-article'}]}}).encode()
            else:
                raw = ('<html><main>Synthetic mechanics evidence ' + 'Synthetic bounded source text. ' * (1000 if large_context else 20) + '</main></html>').encode()
            return {'raw': raw, 'final_url': url}
    if verdict == 'INVALID_DRAFT':
        with pytest.raises(ValueError, match='literal'):
            research.run_cycle(tmp_path, model=SyntheticModel(), fetcher=SyntheticNetwork())
        store = Store(tmp_path)
        assert store.snapshot()['cycles'][0]['status'] == 'FAILED'
        assert len(store.events('model_call_reserved')) == 2
        assert len(store.events('research_draft_rejected')) == 1
        assert store.snapshot()['queue'] == []
        assert store.snapshot()['counts']['cards'] == (6 if large_context else 0)
        return
    result = research.run_cycle(tmp_path, model=SyntheticModel(), fetcher=SyntheticNetwork())
    snapshot = Store.read_snapshot(tmp_path)
    assert result['status'] == 'COMPLETED'
    assert [p[0] for p in prompts] == ['research_planner', 'knowledge_researcher', 'independent_critic']
    assert 'SYNTHETIC Batch001 prior' in prompts[0][1]
    assert len(Store(tmp_path).events('model_call_reserved')) == 3
    assert snapshot['counts']['queue'] == 4 and snapshot['counts']['cards'] == (7 if large_context else 1)
    assert {q['status'] for q in snapshot['queue']} == ({'PROPOSED'} if verdict == 'ACCEPT_AS_PROPOSAL' else {'REJECTED'})
    assert all(q['execution_enabled'] is False for q in snapshot['queue'])
    assert all(q['plan']['hypothesis_version'] == 1 for q in snapshot['queue'])
    assert snapshot['cards'][-1]['status'] == ('EVIDENCE_BACKED_CLAIM' if verdict == 'ACCEPT_AS_PROPOSAL' else 'REJECTED_DRAFT')
    assert snapshot['cycles'][0]['status'] == 'COMPLETED'
    assert snapshot['counts']['gaps'] >= 2
    assert len(list((tmp_path / 'phase3/reports').glob('*.json'))) == 1


def test_network_failure_preserves_prior_response_and_consumed_call(tmp_path, monkeypatch):
    import lab3.research as research
    from lab3.store import Store
    monkeypatch.setattr(research, 'verify_baseline', lambda root: {'verified': True, 'synthetic': True})
    monkeypatch.setattr(research, 'load_prior', lambda root: {'scope': 'Synthetic prior'})
    class SyntheticPlanner:
        def complete(self, role, prompt):
            assert role == 'research_planner'
            return {'questions_th': ['ข้อจำกัดสังเคราะห์'], 'queries': {f: f for f in FAMILIES}}
    class SyntheticFailingNetwork:
        count = 0
        def get(self, url, allowed):
            self.count += 1
            if self.count == 2:
                raise OSError('Synthetic network failure, no fallback')
            return {'raw': b'{"message":{"items":[]}}', 'final_url': url}
    with pytest.raises(OSError, match='Synthetic network failure'):
        research.run_cycle(tmp_path, model=SyntheticPlanner(), fetcher=SyntheticFailingNetwork())
    store = Store(tmp_path)
    assert store.snapshot()['cycles'][0]['status'] == 'FAILED'
    assert store.snapshot()['cards'] == []
    assert len(store.events('model_call_reserved')) == 1
    assert len(store.events('network_failure')) >= 1
    responses = store.events('network_response')
    assert len(responses) == 1
    assert responses[0]['payload']['raw_snapshot'] == '{"message":{"items":[]}}'
    assert not (tmp_path / 'phase3/reports').exists()


def test_prior_findings_and_existing_history_are_bounded_read_only():
    from pathlib import Path
    import json
    import hashlib
    from lab3.research import load_prior, verify_baseline, _compact
    root = Path(__file__).resolve().parents[2]
    baseline = json.loads((root / 'dashboard/qa/baseline-evidence.json').read_text())
    before = {p: (hashlib.sha256((root / p).read_bytes()).hexdigest(), (root / p).stat().st_mtime_ns) for p in baseline}
    assert verify_baseline(root)['file_count'] == 56
    prior = load_prior(root)
    assert len(prior['original_cards']) == 2
    assert 'not new performance' in prior['scope']
    history = [{'id': 'synthetic-' + str(i), 'text': 'SYNTHETIC ' * 4000} for i in range(30)]
    assert len(json.dumps(_compact(history))) < 4000
    after = {p: (hashlib.sha256((root / p).read_bytes()).hexdigest(), (root / p).stat().st_mtime_ns) for p in baseline}
    assert before == after


def test_critic_accepts_only_exact_schema_and_explicit_empty_issues():
    accepted = {'verdict': 'ACCEPT_AS_PROPOSAL', 'issues': [], 'lessons_th': [], 'next_questions': []}
    assert validate_critic(accepted)['verdict'] == 'ACCEPT_AS_PROPOSAL'
    for bad in [dict(accepted, issues=['critical flaw']), dict(accepted, issues=None),
                {'verdict': 'ACCEPT_AS_PROPOSAL'}, dict(accepted, approved=True)]:
        with pytest.raises(ValueError):
            validate_critic(bad)
