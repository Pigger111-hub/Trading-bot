"""Versioned evidence-backed knowledge; no automatic FACT promotion or executable skills."""
from pathlib import Path
import re

from .registry import canonical, digest


def nonempty(value, name, maximum=12000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'invalid {name}')
    return value


def normalize(text):
    return ' '.join(text.split()).casefold()


class KnowledgeStore:
    def __init__(self, root, registry):
        self.root = Path(root)
        self.registry = registry

    def cards(self):
        return [event['payload'] for event in self.registry.events('knowledge_card')]

    def record_card(self, card, sources, critique):
        self.registry.verify()
        if card.get('kind') != 'EVIDENCE_BACKED_CLAIM':
            raise ValueError('automatic FACT promotion forbidden; only EVIDENCE_BACKED_CLAIM')
        topic = nonempty(card.get('topic'), 'topic', 300)
        nonempty(card.get('explanation_th'), 'Thai explanation')
        if not re.search('[\u0e00-\u0e7f]', card['explanation_th']):
            raise ValueError('Thai beginner explanation required')
        if critique.get('verdict') != 'SUPPORTED' or critique.get('issues') != []:
            raise ValueError('independent critic has not supported the card')
        source_map = {source['source_id']: source for source in sources}
        claims = card.get('claims')
        if not isinstance(claims, list) or not 1 <= len(claims) <= 8:
            raise ValueError('1..8 source-backed claims required')
        for claim in claims:
            nonempty(claim.get('statement_th'), 'statement', 2000)
            quote = nonempty(claim.get('quote'), 'verbatim quote', 1000)
            if len(quote.split()) < 4:
                raise ValueError('verbatim quote too short for meaningful evidence')
            source = source_map.get(claim.get('source_id'))
            if not source or normalize(quote) not in normalize(source['text']):
                raise ValueError('claim requires a verbatim quote from a retrieved source')
        for key in ('uncertainties_th', 'next_questions'):
            if not isinstance(card.get(key), list) or not 1 <= len(card[key]) <= 5:
                raise ValueError(f'1..5 {key} required')
            for value in card[key]:
                nonempty(value, key, 1000)
        prior = [item for item in self.cards() if item['card']['topic'] == topic]
        record = {'card': card, 'version': len(prior) + 1,
                  'supersedes': prior[-1]['card_id'] if prior else None,
                  'sources': [{key: source[key] for key in ('source_id', 'url', 'retrieved_at')}
                              for source in sources], 'critique': critique,
                  'verification_scope': 'Exact quote presence + model support review; NOT universal truth.'}
        record['card_id'] = digest(record)
        target = self.root / 'knowledge/cards' / (record['card_id'] + '.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as handle:
            handle.write(canonical(record))
        self.registry.append('knowledge_card', record)
        return record['card_id']

    def propose_skill(self, title, rationale, procedure_text, evidence_ids):
        nonempty(title, 'title', 300)
        nonempty(rationale, 'rationale')
        nonempty(procedure_text, 'inert proposal')
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError('documented evidence required')
        known = {event['hash'] for event in self.registry.events()}
        known.update(card['card_id'] for card in self.cards())
        if not all(item in known for item in evidence_ids):
            raise ValueError('unknown evidence')
        return self.registry.append('skill_proposal', {'title': title, 'rationale': rationale,
                                   'procedure_text': procedure_text, 'evidence_ids': evidence_ids,
                                   'status': 'PENDING_HUMAN_REVIEW', 'activated': False})
