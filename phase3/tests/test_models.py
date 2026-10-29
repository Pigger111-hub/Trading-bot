"""Synthetic Hermes streams and subprocesses only; never calls a provider."""
import json
import subprocess
import pytest
from lab3.models import HermesModel, ModelError, parse_hermes_stream
from lab3.store import Store


def stream(value):
    return json.dumps({'type': 'result', 'exit_code': 0, 'text': json.dumps(value), 'tokens': 4})


def test_parser_strict_result_and_tool_denial():
    assert parse_hermes_stream(stream({'synthetic': True}))[0] == {'synthetic': True}
    for text in [stream({}) + '\n' + stream({}), '{"type":"result","exit_code":1,"text":"{}"}',
                 '{"type":"tool_use"}\n' + stream({}),
                 '{"type":"result","exit_code":0,"text":"{\\"x\\":NaN}"}',
                 '{"type":"result","exit_code":0}', stream([]),
                 '{"type":"assistant","tool_calls":[{}]}\n' + stream({}),
                 '{"type":"tool_call_start"}\n' + stream({}),
                 '{"type":"result","exit_code":0,"is_error":true,"text":"{}"}',
                 '{"type":"result","exit_code":0,"text":"{\\"x\\":1e999}"}',
                 '{"type":"result","exit_code":0,"text":"{\\"x\\":1,\\"x\\":2}"}']:
        with pytest.raises(ModelError):
            parse_hermes_stream(text)


def test_actual_failed_subprocess_consumes_all_three_reservations(tmp_path, monkeypatch):
    store = Store(tmp_path)
    cycle = store.start_cycle()
    monkeypatch.setattr('shutil.which', lambda name: 'hermes')
    monkeypatch.setattr('lab3.models._bounded_process', lambda *a, **k: (b'SYNTHETIC INVALID OUTPUT', b'SYNTHETIC FAILURE', 1))
    model = HermesModel(store, cycle['id'])
    for role in ('research_planner', 'knowledge_researcher', 'independent_critic'):
        with pytest.raises(ModelError):
            model.complete(role, 'Synthetic failing prompt')
    with pytest.raises(ValueError):
        model.complete('research_planner', 'fourth denied')
    assert len(store.events('model_call_failed')) == 3
    assert len(store.events('model_raw_response')) == 3


def test_timeout_preserves_partial_model_response(tmp_path, monkeypatch):
    store = Store(tmp_path)
    cycle = store.start_cycle()
    monkeypatch.setattr('shutil.which', lambda name: 'hermes')
    def synthetic_timeout(*a, **k):
        raise subprocess.TimeoutExpired('SYNTHETIC', 150, output=b'SYNTHETIC PARTIAL', stderr=b'SYNTHETIC DIAGNOSTIC')
    monkeypatch.setattr('lab3.models._bounded_process', synthetic_timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        HermesModel(store, cycle['id']).complete('research_planner', 'Synthetic timeout')
    assert store.events('model_raw_response')[0]['payload']['stdout'] == 'SYNTHETIC PARTIAL'
    assert len(store.events('model_call_reserved')) == 1


def test_bounded_subprocess_timeout_includes_nonreading_stdin(tmp_path):
    import sys
    from lab3.models import _bounded_process
    with pytest.raises(subprocess.TimeoutExpired):
        _bounded_process([sys.executable, '-c', 'import time;time.sleep(5)'], input=b'x' * 1_000_000,
                         timeout=0.1, cwd=tmp_path, env={}, shell=False)


def test_call_reservation_precedes_execution_and_failures_consume_cap(tmp_path, monkeypatch):
    store = Store(tmp_path)
    cycle = store.start_cycle()
    def synthetic_process(command, **kwargs):
        assert len(store.events('model_call_reserved')) >= 1
        assert kwargs['shell'] is False
        assert kwargs['timeout'] == 150
        assert '--safe-mode' in command and command[command.index('--toolsets') + 1] == 'bot_room'
        assert 'scratch' in str(kwargs['cwd'])
        assert 'BINANCE_API_KEY' not in kwargs['env']
        return b'{"type":"result","exit_code":0,"text":"{\\"synthetic\\":true}"}', b'', 0
    monkeypatch.setenv('BINANCE_API_KEY', 'SYNTHETIC-NOT-A-CREDENTIAL')
    monkeypatch.setattr('lab3.models._bounded_process', synthetic_process)
    monkeypatch.setattr('shutil.which', lambda name: 'hermes')
    model = HermesModel(store, cycle['id'])
    assert model.complete('research_planner', 'Synthetic prompt') == {'synthetic': True}
    model.complete('knowledge_researcher', 'Synthetic prompt')
    model.complete('independent_critic', 'Synthetic prompt')
    with pytest.raises(ValueError):
        model.complete('research_planner', 'fourth forbidden')
    assert len(store.events('model_call_completed')) == 3
