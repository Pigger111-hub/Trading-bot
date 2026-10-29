"""Synthetic CLI tests: local scratch state only, no network/model calls."""
import json
import pytest
from lab3.cli import main
from lab3.store import Store


def test_status_is_read_only_and_execution_commands_do_not_exist(tmp_path, capsys):
    assert main(['--root', str(tmp_path), 'status']) == 0
    assert json.loads(capsys.readouterr().out)['available'] is False
    assert not (tmp_path / 'phase3').exists()
    for command in ('execute', 'backtest', 'scheduler'):
        with pytest.raises(SystemExit):
            main(['--root', str(tmp_path), command])


def test_explicit_recovery_never_replays_model_calls(tmp_path, capsys):
    store = Store(tmp_path)
    cycle = store.start_cycle()
    store.reserve_model_call(cycle['id'], 'research_planner')
    assert main(['--root', str(tmp_path), 'recover', '--reason', 'Synthetic interrupted worker confirmed stopped']) == 0
    snap = Store.read_snapshot(tmp_path)
    assert snap['cycles'][0]['status'] == 'INTERRUPTED'
    assert len(store.events('model_call_reserved')) == 1
    assert main(['--root', str(tmp_path), 'recover', '--reason', 'No active cycle']) == 1


def test_human_source_metadata_review_requires_reason_and_reviewer(tmp_path, capsys):
    store = Store(tmp_path)
    store.put('sources', {'id': 'synthetic-doi', 'status': 'VERIFIED_METADATA_PENDING_HUMAN_APPROVAL', 'approved': False})
    assert main(['--root', str(tmp_path), 'approve-source', 'synthetic-doi', '--reviewer', 'Synthetic Human', '--reason', 'Metadata inspected']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['approved'] is True and result['evidence_scope'] == 'METADATA_REVIEW_ONLY'


def test_run_returns_failure_nonzero_without_hiding_error(tmp_path, monkeypatch, capsys):
    def synthetic_failure(root):
        raise ValueError('Synthetic persisted failure')
    monkeypatch.setattr('lab3.cli.run_cycle', synthetic_failure)
    assert main(['--root', str(tmp_path), 'run']) == 1
    assert 'Synthetic persisted failure' in capsys.readouterr().err
