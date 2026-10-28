import json
import pytest


def test_cli_status_and_paper_command_fail_closed(tmp_path, capsys):
    from trading_lab.cli import main
    from test_governance import synthetic_policy
    (tmp_path / 'governance').mkdir()
    (tmp_path / 'governance/safety-policy.json').write_text(json.dumps(synthetic_policy()), encoding='utf-8')
    assert main(['--root', str(tmp_path), 'status']) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['live_orders'] is False
    assert output['scheduler_enabled'] is False
    assert output['approvals'] == 0
    with pytest.raises(SystemExit):
        main(['--root', str(tmp_path), 'paper'])


@pytest.mark.parametrize('command', ['research', 'experiment'])
@pytest.mark.parametrize('failed', [[{'error': 'synthetic fault'}], 'synthetic failure', []])
def test_cli_loop_failure_is_nonzero_and_preserves_json(tmp_path, monkeypatch, capsys, command, failed):
    import trading_lab.cli as cli
    from trading_lab.research import KnowledgeLoop
    from trading_lab.runner import ExperimentLoop
    from test_governance import synthetic_policy
    (tmp_path / 'governance').mkdir()
    (tmp_path / 'governance/safety-policy.json').write_text(json.dumps(synthetic_policy()), encoding='utf-8')
    expected = {'completed': ['synthetic-completion'], 'failed': failed}
    monkeypatch.setattr(cli, '_model', lambda *args: None)
    monkeypatch.setattr(cli, '_spec', lambda *args: {'spec_id': 'a' * 64})
    monkeypatch.setattr(KnowledgeLoop, 'run', lambda *args: expected)
    monkeypatch.setattr(ExperimentLoop, 'run', lambda *args: expected)
    argv = ['--root', str(tmp_path), command]
    if command == 'experiment':
        argv += ['--spec', 'a' * 64]
    assert cli.main(argv) == (2 if failed else 0)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == expected
    assert captured.err == ''


@pytest.mark.parametrize('with_provenance', [True, False])
def test_cli_spec_binds_provenance_and_full_data_window(tmp_path, monkeypatch, capsys, with_provenance):
    import pandas as pd
    import trading_lab.cli as cli
    import trading_lab.data as data
    from test_governance import synthetic_policy
    (tmp_path / 'governance').mkdir()
    (tmp_path / 'governance/safety-policy.json').write_text(json.dumps(synthetic_policy()), encoding='utf-8')
    frame = pd.DataFrame({column: range(180) for column in ('Open', 'High', 'Low', 'Close', 'Volume')},
                         index=pd.date_range('2020-01-01', periods=180, freq='h', tz='UTC'))
    manifest = {'sha256': 'd' * 64}
    if with_provenance:
        manifest['dataset_sha256'] = 'a' * 64
    monkeypatch.setattr(data, 'load_snapshot', lambda *args: (frame, manifest))
    monkeypatch.setattr(cli, 'code_hash', lambda *args: 'b' * 64)
    status = cli.main(['--root', str(tmp_path), 'spec', '--dataset', 'c' * 32])
    captured = capsys.readouterr()
    if with_provenance:
        assert status == 0
        spec = json.loads(captured.out)
        assert spec['dataset_hash'] == 'a' * 64
        assert spec['data_window'] == [frame.index[0].isoformat(), frame.index[-1].isoformat()]
        assert spec['status'] == 'PENDING_HUMAN_APPROVAL'
        assert spec['executed'] is False
    else:
        assert status == 2
        assert json.loads(captured.err)['failed_closed'] is True
        assert not (tmp_path / 'governance/specs').exists()


def test_dataset_identifiers_match_ingestion_uuid_format():
    from trading_lab.cli import _dataset_identifier
    assert _dataset_identifier('a' * 32) == 'a' * 32
    with pytest.raises(ValueError):
        _dataset_identifier('../' + 'a' * 32)
