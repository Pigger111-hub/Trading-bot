"""Additional SYNTHETIC data quality and bounded-request regression tests."""
import pandas as pd
import pytest

import trading_lab.data as api
from test_data import START, HOUR, SyntheticResponse, install_http, synthetic_kline


def test_missing_leading_candle_is_not_silently_accepted(tmp_path, monkeypatch):
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(1)])])
    with pytest.raises(ValueError, match='coverage'):
        api.download_snapshot(tmp_path, start_ms=START, end_ms=START + 2 * HOUR)


def test_excessive_ingestion_range_fails_before_network(tmp_path, monkeypatch):
    session = install_http(monkeypatch, [])
    with pytest.raises(ValueError, match='budget'):
        api.download_snapshot(tmp_path, start_ms=START, end_ms=START + 40000 * HOUR)
    assert session.calls == []


def test_boolean_prices_are_not_valid_market_data():
    frame = pd.DataFrame({key: [True, True] for key in api.COLUMNS},
                         index=pd.date_range('2020-01-01', periods=2, freq='h', tz='UTC'))
    with pytest.raises(ValueError):
        api.validate_frame(frame)
