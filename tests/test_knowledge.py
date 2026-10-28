import pytest

from trading_lab.registry import Registry


def test_cards_require_verbatim_evidence_and_cannot_be_promoted_to_fact(tmp_path):
    from trading_lab.knowledge import KnowledgeStore
    registry = Registry(tmp_path / 'lab.sqlite')
    store = KnowledgeStore(tmp_path, registry)
    source = {'source_id': 'a'*64, 'url': 'https://kernc.github.io/backtesting.py/',
              'text': 'Synthetic fixture. Commission is charged on entry and exit.',
              'retrieved_at': '2026-01-01T00:00:00+00:00'}
    card = {'topic': 'synthetic fees', 'explanation_th': 'นี่คือข้อมูลทดสอบ ไม่ใช่ผลวิจัย',
            'claims': [{'statement_th': 'ข้อความทดสอบ', 'source_id': 'a'*64,
                        'quote': 'Commission is charged on entry and exit.'}],
            'uncertainties_th': ['ข้อมูลสังเคราะห์'], 'next_questions': ['synthetic spread'],
            'kind': 'EVIDENCE_BACKED_CLAIM'}
    first = store.record_card(card, [source], {'verdict': 'SUPPORTED', 'issues': []})
    assert store.cards()[0]['card_id'] == first
    card['kind'] = 'FACT'
    with pytest.raises(ValueError, match='FACT'):
        store.record_card(card, [source], {'verdict': 'SUPPORTED', 'issues': []})
    card['kind'] = 'EVIDENCE_BACKED_CLAIM'
    card['claims'][0]['quote'] = 'This statement does not exist.'
    with pytest.raises(ValueError, match='verbatim'):
        store.record_card(card, [source], {'verdict': 'SUPPORTED', 'issues': []})
    assert len(store.cards()) == 1
