"""Synthetic model/network fixtures test the loop, not research results."""
from trading_lab.registry import Registry
from test_governance import synthetic_policy


def test_knowledge_loop_adapts_to_model_gap_and_preserves_history(tmp_path, monkeypatch):
    from trading_lab.research import KnowledgeLoop
    import trading_lab.research as module
    topics = []

    def synthetic_fetch(root, url):
        return {'source_id': 'a'*64, 'url': url, 'text': 'Synthetic evidence costs reduce returns.',
                'retrieved_at': '2026-01-01T00:00:00+00:00'}

    class SyntheticModel:
        def complete(self, role, prompt):
            if role == 'knowledge_critic':
                return {'verdict': 'SUPPORTED', 'issues': []}
            topic = 'fees commission' if not topics else 'lookahead bias'
            topics.append(topic)
            return {'kind': 'EVIDENCE_BACKED_CLAIM', 'topic': topic,
                    'explanation_th': 'ตัวอย่างสังเคราะห์สำหรับทดสอบวงจรเท่านั้น',
                    'claims': [{'statement_th': 'หลักฐานสังเคราะห์', 'source_id': 'a'*64,
                                'quote': 'Synthetic evidence costs reduce returns.'}],
                    'uncertainties_th': ['ยังไม่ใช่ผลวิจัยจริง'], 'next_questions': ['lookahead bias']}

    monkeypatch.setattr(module, 'fetch_source', synthetic_fetch)
    registry = Registry(tmp_path / 'lab.sqlite')
    result = KnowledgeLoop(tmp_path, registry, SyntheticModel(), synthetic_policy()).run(
        cycles=2, seed_topics=['fees commission'])
    assert result['completed'] == 2
    assert topics == ['fees commission', 'lookahead bias']
    assert len(registry.events('knowledge_card')) == 2
    assert registry.verify() > 0
