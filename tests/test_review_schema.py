"""Validate reviews directly; never exercise interactive human approval."""
import pytest


def valid_review():
    return {'passed': True, 'code_hash': 'a' * 64, 'reviewer': 'independent reviewer',
            'security_concerns': [], 'logic_errors': []}


@pytest.mark.parametrize('field,value', [
    ('passed', 1), ('passed', 'true'), ('passed', False),
    ('code_hash', 'not-a-hash'), ('code_hash', 'b' * 64), ('code_hash', None),
    ('reviewer', ''), ('reviewer', '  '), ('reviewer', 1), ('reviewer', []),
    ('security_concerns', None), ('security_concerns', ''),
    ('security_concerns', {}), ('security_concerns', ['issue']),
    ('logic_errors', None), ('logic_errors', ''), ('logic_errors', {}),
    ('logic_errors', ['issue']), ('review_id', ''), ('review_id', '  '),
    ('review_id', None), ('review_id', 1),
])
def test_review_schema_rejects_invalid_fields(field, value):
    from trading_lab.cli import validate_review
    review = {**valid_review(), field: value}
    with pytest.raises(ValueError):
        validate_review(review, 'a' * 64)


@pytest.mark.parametrize('field', ['passed', 'code_hash', 'reviewer', 'security_concerns', 'logic_errors'])
def test_review_schema_requires_explicit_fields(field):
    from trading_lab.cli import validate_review
    review = valid_review()
    del review[field]
    with pytest.raises(ValueError):
        validate_review(review, 'a' * 64)


@pytest.mark.parametrize('review', [None, [], '', True])
def test_review_schema_requires_json_object(review):
    from trading_lab.cli import validate_review
    with pytest.raises(ValueError):
        validate_review(review, 'a' * 64)


def test_review_schema_accepts_only_explicit_clean_matching_review():
    from trading_lab.cli import validate_review
    validate_review(valid_review(), 'a' * 64)
    validate_review({**valid_review(), 'review_id': 'independent-review-1'}, 'a' * 64)
    with pytest.raises(ValueError):
        validate_review({**valid_review(), 'code_hash': 'invalid'}, 'invalid')
