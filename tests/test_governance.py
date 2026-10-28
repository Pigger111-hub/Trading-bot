"""Tests use synthetic approvals/specs, not permission to run market experiments."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from trading_lab.registry import Registry


def synthetic_policy():
    return {'mode': 'research_only', 'market': 'spot', 'symbols': ['BTCUSDT'], 'intervals': ['1h'],
            'allow_credentials': False, 'allow_live_orders': False, 'allow_paper_loop': False,
            'allow_short': False, 'leverage': 1, 'max_position_fraction': 0.1,
            'max_batch_runs': 8, 'max_research_cycles': 3, 'max_model_calls_per_cycle': 3,
            'scheduler_enabled': False, 'allow_dynamic_code': False, 'version': 1}


def test_missing_approval_and_risk_changes_fail_closed(tmp_path):
    from trading_lab.governance import authorize_run, make_spec, policy_hash
    policy = synthetic_policy()
    spec = make_spec('a'*64, 'b'*64, policy, [{'fast': 5, 'slow': 20}], budget=1)
    registry = Registry(tmp_path / 'lab.sqlite')
    with pytest.raises(PermissionError, match='approval'):
        authorize_run(registry, spec, policy, 'b'*64, 'a'*64, {'fast': 5, 'slow': 20})
    registry.append('approval', {'spec_id': spec['spec_id'], 'policy_hash': policy_hash(policy),
                               'code_hash': 'b'*64, 'review_id': 'synthetic-review',
                               'isolation': 'trusted_builtin_process', 'human': 'synthetic-unit-test'})
    policy['leverage'] = 2
    with pytest.raises(PermissionError):
        authorize_run(registry, spec, policy, 'b'*64, 'a'*64, {'fast': 5, 'slow': 20})


def test_budget_is_atomic_and_configuration_cannot_be_repeated(tmp_path):
    from trading_lab.governance import authorize_run, make_spec, policy_hash
    policy = synthetic_policy()
    spec = make_spec('a'*64, 'b'*64, policy, [{'fast': 5, 'slow': 20}], budget=1)
    registry = Registry(tmp_path / 'lab.sqlite')
    registry.append('approval', {'spec_id': spec['spec_id'], 'policy_hash': policy_hash(policy),
                               'code_hash': 'b'*64, 'review_id': 'synthetic-review',
                               'isolation': 'trusted_builtin_process', 'human': 'synthetic-unit-test'})
    def reserve(_):
        try:
            return authorize_run(registry, spec, policy, 'b'*64, 'a'*64, {'fast': 5, 'slow': 20})
        except PermissionError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(4)))
    assert sum(result is not None for result in results) == 1
    assert len(registry.events('run_reserved')) == 1


def test_holdout_fingerprint_ignores_snapshot_id_but_detects_final_data_changes():
    import numpy as np
    import pandas as pd
    from trading_lab.governance import holdout_fingerprint
    values = np.arange(180, dtype=float) + 100
    frame = pd.DataFrame({key: values.copy() for key in ['Open', 'High', 'Low', 'Close', 'Volume']},
                         index=pd.date_range('2020-01-01', periods=180, freq='h', tz='UTC'))
    first = holdout_fingerprint(frame)
    frame.iloc[0] *= 2
    assert holdout_fingerprint(frame) == first
    frame.iloc[-1] *= 2
    assert holdout_fingerprint(frame) != first


def test_holdout_cannot_be_reused_by_a_new_specification(tmp_path):
    from trading_lab.governance import authorize_run, make_spec, policy_hash
    policy = synthetic_policy()
    registry = Registry(tmp_path / 'lab.sqlite')
    first = make_spec('a'*64, 'b'*64, policy, [{'fast': 5, 'slow': 20}], budget=1)
    second = make_spec('a'*64, 'b'*64, policy, [{'fast': 6, 'slow': 20}], budget=1)
    for spec in (first, second):
        registry.append('approval', {'spec_id': spec['spec_id'], 'policy_hash': policy_hash(policy),
                                   'code_hash': 'b'*64, 'review_id': 'synthetic-review',
                                   'isolation': 'trusted_builtin_process', 'human': 'synthetic-unit-test'})
    authorize_run(registry, first, policy, 'b'*64, 'a'*64, first['parameters'][0])
    with pytest.raises(PermissionError, match='holdout'):
        authorize_run(registry, second, policy, 'b'*64, 'a'*64, second['parameters'][0])


def test_overlapping_holdout_windows_are_not_fresh_evidence(tmp_path):
    from trading_lab.governance import authorize_run, make_spec, policy_hash
    policy = synthetic_policy()
    registry = Registry(tmp_path / 'lab.sqlite')
    windows = [['2026-01-01T00:00:00+00:00', '2026-02-01T00:00:00+00:00'],
               ['2026-01-15T00:00:00+00:00', '2026-02-15T00:00:00+00:00']]
    specs = [make_spec('a'*64, 'b'*64, policy, [{'fast': 5, 'slow': 20}], budget=1,
                       holdout_hash=letter*64, holdout_window=window)
             for letter, window in zip(['c', 'd'], windows)]
    for spec in specs:
        registry.append('approval', {'spec_id': spec['spec_id'], 'policy_hash': policy_hash(policy),
            'code_hash': 'b'*64, 'review_id': 'synthetic-review', 'isolation': 'trusted_builtin_process',
            'human': 'synthetic-unit-test'})
    authorize_run(registry, specs[0], policy, 'b'*64, 'a'*64, specs[0]['parameters'][0])
    with pytest.raises(PermissionError, match='holdout'):
        authorize_run(registry, specs[1], policy, 'b'*64, 'a'*64, specs[1]['parameters'][0])


def test_previous_development_or_evaluation_data_cannot_become_a_fresh_holdout(tmp_path):
    import pandas as pd
    from trading_lab.governance import authorize_run, make_spec, policy_hash
    times = pd.date_range('2020-01-01', periods=180, freq='h', tz='UTC')
    policy = synthetic_policy()
    registry = Registry(tmp_path / 'lab.sqlite')
    specifications = [
        make_spec('a'*64, 'b'*64, policy, [{'fast': 5, 'slow': 20}], budget=1,
                  holdout_hash='c'*64, holdout_window=[times[150].isoformat(), times[179].isoformat()],
                  data_window=[times[0].isoformat(), times[179].isoformat()]),
        make_spec('d'*64, 'b'*64, policy, [{'fast': 5, 'slow': 20}], budget=1,
                  holdout_hash='e'*64, holdout_window=[times[125].isoformat(), times[149].isoformat()],
                  data_window=[times[0].isoformat(), times[149].isoformat()])]
    for spec in specifications:
        registry.append('approval', {'spec_id': spec['spec_id'], 'policy_hash': policy_hash(policy),
            'code_hash': 'b'*64, 'review_id': 'synthetic-review', 'isolation': 'trusted_builtin_process',
            'human': 'synthetic-unit-test'})
    first, second = specifications
    authorize_run(registry, first, policy, 'b'*64, first['dataset_hash'], first['parameters'][0])
    with pytest.raises(PermissionError, match='exposed'):
        authorize_run(registry, second, policy, 'b'*64, second['dataset_hash'], second['parameters'][0])


def test_same_predeclared_batch_can_run_without_per_configuration_approval(tmp_path):
    from trading_lab.governance import authorize_run, make_spec, policy_hash
    policy = synthetic_policy()
    registry = Registry(tmp_path / 'lab.sqlite')
    parameters = [{'fast': 5, 'slow': 20}, {'fast': 6, 'slow': 20}]
    specification = make_spec('a'*64, 'b'*64, policy, parameters, budget=2,
        holdout_window=['2020-02-01T00:00:00+00:00', '2020-02-15T00:00:00+00:00'],
        data_window=['2020-01-01T00:00:00+00:00', '2020-02-15T00:00:00+00:00'])
    registry.append('approval', {'spec_id': specification['spec_id'], 'policy_hash': policy_hash(policy),
        'code_hash': 'b'*64, 'review_id': 'synthetic-review', 'isolation': 'trusted_builtin_process',
        'human': 'synthetic-unit-test'})
    for parameters in specification['parameters']:
        assert authorize_run(registry, specification, policy, 'b'*64, 'a'*64, parameters)
    assert len(registry.events('approval')) == 1
    assert len(registry.events('run_reserved')) == 2
    assert len(registry.events('holdout_exposed')) == 1


def test_executable_hash_covers_nested_modules(tmp_path):
    from trading_lab.governance import code_hash
    source = tmp_path / 'src/trading_lab/subpackage'
    source.mkdir(parents=True)
    (tmp_path / 'pyproject.toml').write_text('synthetic project', encoding='utf-8')
    (tmp_path / 'uv.lock').write_text('synthetic lock', encoding='utf-8')
    module = source / 'nested.py'
    module.write_text('VALUE = 1', encoding='utf-8')
    first = code_hash(tmp_path)
    module.write_text('VALUE = 2', encoding='utf-8')
    assert code_hash(tmp_path) != first
