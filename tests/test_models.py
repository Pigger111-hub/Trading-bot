import json
import pytest


def test_hermes_stream_parser_rejects_tool_calls_and_missing_result():
    from trading_lab.models import parse_hermes_stream
    good = json.dumps({'type': 'result', 'exit_code': 0, 'text': '{"ok": true}',
                       'tokens': {'total': 12}})
    assert parse_hermes_stream(good)[0] == {'ok': True}
    with pytest.raises(RuntimeError, match='tool'):
        parse_hermes_stream(json.dumps({'type': 'tool_use', 'name': 'terminal'}) + '\n' + good)
    with pytest.raises(RuntimeError, match='result'):
        parse_hermes_stream('not a model response')
