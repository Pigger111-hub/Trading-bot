"""Synthetic lifecycle tests; never market experiments."""
import sqlite3

import pytest


def test_event_history_is_append_only_and_tampering_detected(tmp_path):
    from trading_lab.registry import Registry
    registry = Registry(tmp_path / 'lab.sqlite')
    first = registry.append('lesson', {'text': 'synthetic finding', 'kind': 'FINDING'})
    second = registry.append('lesson', {'supersedes': first, 'text': 'correction'})
    assert first != second
    assert registry.verify() == 2
    assert registry.events('lesson')[0]['payload']['text'] == 'synthetic finding'
    with sqlite3.connect(registry.path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE events SET payload='{}' WHERE id=1")
    assert registry.verify() == 2
