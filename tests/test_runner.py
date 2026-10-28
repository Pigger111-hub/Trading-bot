"""Synthetic runner gates: no real strategy execution is approved by these tests."""
import pytest

from trading_lab.registry import Registry
from test_governance import synthetic_policy


def test_runner_denies_unapproved_batch_before_starting_subprocess(tmp_path, monkeypatch):
    from trading_lab.runner import ExperimentLoop
    from trading_lab.governance import make_spec
    import trading_lab.runner as module
    called = []
    monkeypatch.setattr(module, 'isolated_backtest', lambda *args, **kwargs: called.append(True))
    registry = Registry(tmp_path / 'lab.sqlite')
    spec = make_spec('a'*64, 'b'*64, synthetic_policy(), [{'fast': 5, 'slow': 20}], budget=1)
    loop = ExperimentLoop(tmp_path, registry, synthetic_policy())
    with pytest.raises(PermissionError, match='approval'):
        loop.reserve(spec, 'b'*64, 'a'*64, {'fast': 5, 'slow': 20})
    assert called == []


def test_approved_synthetic_batch_runs_learns_and_never_repeats(tmp_path, monkeypatch):
    import json
    import numpy as np
    import pandas as pd
    from trading_lab.governance import holdout_fingerprint, make_spec, policy_hash
    from trading_lab.runner import ExperimentLoop
    import trading_lab.data as data_module
    import trading_lab.runner as runner_module
    policy = synthetic_policy()
    (tmp_path / 'governance').mkdir()
    (tmp_path / 'governance/safety-policy.json').write_text(json.dumps(policy), encoding='utf-8')
    values = 30000 + np.sin(np.arange(180) / 5) * 1000
    frame = pd.DataFrame({'Open': values, 'High': values+5, 'Low': values-5,
                          'Close': values, 'Volume': 1.0},
                         index=pd.date_range('2020-01-01', periods=180, freq='h', tz='UTC'))
    window = [frame.index[-30].isoformat(), frame.index[-1].isoformat()]
    spec = make_spec('a'*64, 'b'*64, policy, [{'fast': 3, 'slow': 8}], budget=1,
                     dataset_id='c'*32, holdout_hash=holdout_fingerprint(frame), holdout_window=window,
                     data_window=[frame.index[0].isoformat(), frame.index[-1].isoformat()])
    monkeypatch.setattr(data_module, 'load_snapshot', lambda *args:
                        (frame, {'sha256': 'd'*64, 'dataset_sha256': 'a'*64}))
    monkeypatch.setattr(runner_module, 'code_hash', lambda *args: 'b'*64)
    registry = Registry(tmp_path / 'lab.sqlite')
    registry.append('approval', {'spec_id': spec['spec_id'], 'policy_hash': policy_hash(policy),
        'code_hash': 'b'*64, 'review_id': 'synthetic-review', 'isolation': 'trusted_builtin_process',
        'human': 'synthetic-unit-test'})
    class SyntheticModel:
        def complete(self, role, prompt):
            if role == 'experiment_critic':
                assert 'fold_evidence' in prompt
                assert 'cost_stress' in prompt
                return {'verdict': 'INCONCLUSIVE', 'issues_th': ['สังเคราะห์'], 'lessons_th': ['ใช้ทดสอบเท่านั้น']}
            return {'hypothesis_th': 'สมมติฐานสังเคราะห์', 'rationale_th': 'ทดสอบเท่านั้น',
                    'proposed_parameters': {'fast': 4, 'slow': 9}, 'uncertainties_th': ['ไม่ใช่ข้อมูลตลาด'],
                    'method_improvement_th': 'เก็บการทดลองที่ล้มเหลวทุกครั้งเพื่อไม่เลือกเฉพาะผลดี'}
    loop = ExperimentLoop(tmp_path, registry, policy, SyntheticModel())
    result = loop.run(spec)
    assert len(result['completed']) == 1
    assert result['failed'] == []
    import hashlib
    from trading_lab.runner import verify_result_artifact
    event = registry.events('experiment_completed')[0]['payload']
    artifact = tmp_path / event['artifact']
    assert event['artifact_sha256'] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    verified = verify_result_artifact(tmp_path, event)
    assert verified == json.loads(artifact.read_text('utf-8'))
    altered = {**verified, 'baselines': {'tampered': True}}
    from trading_lab.registry import canonical
    artifact.write_text(canonical(altered), encoding='utf-8')
    with pytest.raises(ValueError, match='SHA256'):
        verify_result_artifact(tmp_path, event)
    assert len(registry.events('experiment_lesson')) == 1
    assert registry.events('skill_proposal')[0]['payload']['activated'] is False
    assert registry.events('next_experiment_proposed')[0]['payload']['executed'] is False
    assert loop.run(spec)['completed'] == []
    assert len(registry.events('run_reserved')) == 1


@pytest.mark.parametrize('defect', ['missing', 'start', 'end'])
def test_runner_checks_full_data_window_before_reserving(tmp_path, monkeypatch, defect):
    import pandas as pd
    import trading_lab.data as data
    import trading_lab.runner as runner
    from trading_lab.governance import holdout_fingerprint
    frame = pd.DataFrame({column: range(180) for column in ('Open', 'High', 'Low', 'Close', 'Volume')},
                         index=pd.date_range('2020-01-01', periods=180, freq='h', tz='UTC'))
    specification = {'spec_id': 'e' * 64, 'dataset_id': 'c' * 32, 'holdout_hash': holdout_fingerprint(frame),
                     'holdout_window': [frame.index[-30].isoformat(), frame.index[-1].isoformat()],
                     'parameters': []}
    if defect != 'missing':
        specification['data_window'] = [frame.index[1 if defect == 'start' else 0].isoformat(),
                                        frame.index[-2 if defect == 'end' else -1].isoformat()]
    monkeypatch.setattr(data, 'load_snapshot', lambda *args:
                        (frame, {'sha256': 'd' * 64, 'dataset_sha256': 'a' * 64}))
    registry = Registry(tmp_path / 'lab.sqlite')
    loop = runner.ExperimentLoop(tmp_path, registry, synthetic_policy())
    with pytest.raises(PermissionError, match='full data.*window'):
        loop.run(specification)
    assert registry.events() == []


@pytest.mark.parametrize('defect', ['missing_hash', 'bad_hash', 'outside_path', 'wrong_run',
                                   'wrong_spec', 'wrong_parameters', 'noncanonical', 'nonobject'])
def test_result_artifact_verification_fails_closed(tmp_path, defect):
    from trading_lab.registry import canonical, digest
    from trading_lab.runner import verify_result_artifact
    result = {'run_id': 'a' * 64, 'spec_id': 'b' * 64, 'parameters': {'fast': 3, 'slow': 8}}
    target = tmp_path / 'experiments' / ('a' * 64 + '.json')
    target.parent.mkdir()
    target.write_text(canonical(result), encoding='utf-8')
    event = {**result, 'artifact': target.relative_to(tmp_path).as_posix(), 'artifact_sha256': digest(result)}
    if defect == 'missing_hash':
        del event['artifact_sha256']
    elif defect == 'bad_hash':
        event['artifact_sha256'] = ''
    elif defect == 'outside_path':
        event['artifact'] = '../outside.json'
    elif defect == 'wrong_run':
        event['run_id'] = 'c' * 64
    elif defect == 'wrong_spec':
        event['spec_id'] = 'c' * 64
    elif defect == 'wrong_parameters':
        event['parameters'] = {'fast': 4, 'slow': 8}
    elif defect == 'noncanonical':
        import hashlib
        target.write_text(canonical(result) + '\n', encoding='utf-8')
        event['artifact_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    else:
        target.write_text('[]', encoding='utf-8')
        event['artifact_sha256'] = digest([])
    with pytest.raises(ValueError):
        verify_result_artifact(tmp_path, event)


@pytest.mark.parametrize('cap', [1, 2])
def test_learning_respects_two_call_protocol_budget(tmp_path, cap):
    from trading_lab.runner import ExperimentLoop
    policy = synthetic_policy()
    policy['max_model_calls_per_cycle'] = cap
    calls = []

    class SyntheticModel:
        def complete(self, role, prompt):
            calls.append(role)
            return {'verdict': 'INCONCLUSIVE'} if role == 'experiment_critic' else {}

    registry = Registry(tmp_path / 'lab.sqlite')
    loop = ExperimentLoop(tmp_path, registry, policy, SyntheticModel())
    loop._learn({'metrics': {}, 'parameters': {}, 'deterministic_critique': {}}, 'synthetic-evidence')
    if cap < 2:
        assert calls == []
        pending = registry.events('experiment_learning_pending')
        assert len(pending) == 1
        assert pending[0]['payload']['source_event'] == 'synthetic-evidence'
        assert registry.events('experiment_lesson') == []
    else:
        assert calls == ['experiment_critic', 'experiment_researcher']
        assert len(registry.events('next_experiment_proposed')) == 1


def test_critique_never_promotes_simulated_profit_to_real_profit():
    from trading_lab.runner import deterministic_critique
    result = {'metrics': {'return_pct': 20, 'max_drawdown_pct': -10, 'trades': 3},
              'walk_forward': {'folds': []}, 'baselines': {}}
    verdict = deterministic_critique(result)
    assert verdict['verdict'] == 'INCONCLUSIVE'
    assert verdict['real_profit_verified'] is False
    assert verdict['eligible_for_paper'] is False
