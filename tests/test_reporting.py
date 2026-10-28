from trading_lab.registry import Registry


def test_report_clearly_labels_no_experiments_and_does_not_invent_profit(tmp_path):
    from trading_lab.reporting import render_report
    registry = Registry(tmp_path / 'lab.sqlite')
    path = render_report(tmp_path, registry)
    text = path.read_text('utf-8')
    assert 'SIMULATED' in text
    assert 'ยังไม่มี' in text
    assert 'real profit' in text
    assert registry.verify() == 0


def test_report_refuses_tampered_synthetic_experiment_artifact(tmp_path):
    import pytest
    from trading_lab.reporting import render_report
    registry = Registry(tmp_path / 'lab.sqlite')
    target = tmp_path / 'experiments' / ('a' * 64 + '.json')
    target.parent.mkdir()
    target.write_text('{"tampered":true}', encoding='utf-8')
    registry.append('experiment_completed', {'run_id': 'a'*64, 'spec_id': 'b'*64,
        'parameters': {'fast': 3, 'slow': 8}, 'metrics': {}, 'verdict': {'verdict': 'INCONCLUSIVE'},
        'artifact': 'experiments/' + 'a'*64 + '.json', 'artifact_sha256': '0'*64})
    with pytest.raises(ValueError, match='SHA256'):
        render_report(tmp_path, registry)
