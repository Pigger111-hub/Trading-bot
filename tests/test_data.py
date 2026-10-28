"""Deterministic SYNTHETIC fixtures only; never market data or live HTTP."""

import pandas as pd
import pytest
import importlib
import hashlib
import json
import requests
from pathlib import Path

START = 1704067200000  # labelled synthetic times, not observed market data
HOUR = 3_600_000
URL = "https://data-api.binance.vision/api/v3/klines"


def synthetic_kline(offset):
    opened = START + offset * HOUR
    return [opened, "10", "12", "9", "11", "2", opened + HOUR - 1, "0", 1, "0", "0", "0"]


class SyntheticResponse:
    def __init__(self, payload, status=200):
        self.content = json.dumps(payload).encode()
        self.status_code = status

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class SyntheticSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        self.closed = True


def install_http(monkeypatch, responses):
    session = SyntheticSession(responses)
    monkeypatch.setattr(requests, "Session", lambda: session)
    return session


def test_download_paginates_and_preserves_synthetic_raw_bytes(tmp_path, monkeypatch):
    first = SyntheticResponse([synthetic_kline(i) for i in range(1000)])
    second = SyntheticResponse([synthetic_kline(1000)])
    session = install_http(monkeypatch, [first, second])
    api = module()
    assert hasattr(api, "download_snapshot"), "snapshot ingestion missing"
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + 1001 * HOUR)
    assert manifest["rows"] == 1001
    assert manifest["source"] == URL
    assert manifest["start_ms"] == START
    assert manifest["end_ms"] == START + 1001 * HOUR
    assert pd.Timestamp(manifest["fetched_at"]).tz is not None
    parquet = tmp_path / manifest["parquet_path"]
    assert not Path(manifest["parquet_path"]).is_absolute()
    assert hashlib.sha256(parquet.read_bytes()).hexdigest() == manifest["sha256"]
    frame = pd.read_parquet(parquet)
    assert len(frame) == 1001
    assert str(frame.index.tz) == "UTC"
    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Volume"]
    for raw, response in zip(manifest["raw_pages"], [first, second], strict=True):
        assert (tmp_path / raw["path"]).read_bytes() == response.content
        assert raw["sha256"] == hashlib.sha256(response.content).hexdigest()
    saved = tmp_path / manifest["dataset_id"] / "manifest.json"
    assert json.loads(saved.read_text()) == manifest
    assert len(session.calls) == 2
    for url, kwargs in session.calls:
        assert url == URL
        assert kwargs["params"]["limit"] == 1000
        assert kwargs["params"]["symbol"] == "BTCUSDT"
        assert kwargs["params"]["interval"] == "1h"
        assert kwargs["params"]["endTime"] == START + 1001 * HOUR - 1
        assert kwargs["timeout"] == (5, 30)
        assert kwargs["allow_redirects"] is False
    assert session.calls[1][1]["params"]["startTime"] == START + 1000 * HOUR
    assert session.closed


def test_download_rejects_unsupported_requests_before_http(tmp_path, monkeypatch):
    session = install_http(monkeypatch, [])
    api = module()
    for override in [
        {"symbol": "ETHUSDT"},
        {"interval": "1m"},
        {"start_ms": True},
        {"start_ms": 1.5},
        {"start_ms": "1704067200000"},
        {"start_ms": -1},
        {"end_ms": START},
        {"end_ms": START - 1},
        {"end_ms": 10**30},
    ]:
        kwargs = {"start_ms": START, "end_ms": START + HOUR, **override}
        with pytest.raises(ValueError):
            api.download_snapshot(tmp_path, **kwargs)
    assert session.calls == []
    assert list(tmp_path.iterdir()) == []


def test_download_only_keeps_candles_closed_before_end_and_fetch_time(tmp_path, monkeypatch):
    api = module()
    monkeypatch.setattr(api, "_now_ms", lambda: START + 2 * HOUR - 1, raising=False)
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(i) for i in range(3)])])
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + 3 * HOUR)
    assert manifest["rows"] == 1  # candle closing exactly at now is not closed yet
    assert len(json.loads((tmp_path / manifest["raw_pages"][0]["path"]).read_bytes())) == 3
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(i) for i in range(2)])])
    monkeypatch.setattr(api, "_now_ms", lambda: START + 100 * HOUR)
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR + HOUR // 2)
    assert manifest["rows"] == 1  # partial candle at requested end is excluded


def test_download_retries_transient_http_with_bounded_backoff(tmp_path, monkeypatch):
    import time

    delays = []
    monkeypatch.setattr(time, "sleep", delays.append)
    session = install_http(
        monkeypatch,
        [SyntheticResponse({}, 429), SyntheticResponse({}, 503), SyntheticResponse([synthetic_kline(0)])],
    )
    manifest = module().download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert manifest["rows"] == 1
    assert len(session.calls) == 3
    assert delays == [0.5, 1.0]


@pytest.mark.parametrize("failure", [429, 500, requests.Timeout, requests.ConnectionError])
def test_download_exhausts_retries_without_partial_snapshot(tmp_path, monkeypatch, failure):
    import time

    delays = []
    monkeypatch.setattr(time, "sleep", delays.append)
    responses = [
        SyntheticResponse({}, failure) if isinstance(failure, int) else failure("synthetic") for _ in range(3)
    ]
    session = install_http(monkeypatch, responses)
    with pytest.raises(requests.RequestException):
        module().download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert len(session.calls) == 3
    assert delays == [0.5, 1.0]
    assert session.closed
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_redirect_without_following_or_credentials(tmp_path, monkeypatch):
    session = install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)], 302)])
    session.trust_env = True
    with pytest.raises(ValueError, match="redirect|status"):
        module().download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert session.trust_env is False  # no implicit netrc credentials or environment proxies
    assert len(session.calls) == 1
    assert session.calls[0][1]["allow_redirects"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "fault",
    [
        "float_time",
        "string_time",
        "bool_time",
        "seconds",
        "microseconds",
        "wrong_close",
        "duplicate",
        "backward",
        "oversize",
        "shape",
        "object",
    ],
)
def test_download_rejects_malformed_rest_pages(tmp_path, monkeypatch, fault):
    row = synthetic_kline(0)
    payload = [row]
    if fault == "float_time":
        row[0] = float(row[0])
    if fault == "string_time":
        row[0] = str(row[0])
    if fault == "bool_time":
        row[0] = True
    if fault == "seconds":
        row[0] //= 1000
    if fault == "microseconds":
        row[0] *= 1000
    if fault == "wrong_close":
        row[6] = row[0] + 1
    if fault == "duplicate":
        payload = [row, row]
    if fault == "backward":
        row[0] -= HOUR
        row[6] -= HOUR
    if fault == "oversize":
        payload = [synthetic_kline(i) for i in range(1001)]
    if fault == "shape":
        payload = [[START, "10"]]
    if fault == "object":
        payload = {"error": "synthetic failure"}
    session = install_http(monkeypatch, [SyntheticResponse(payload)])
    with pytest.raises(ValueError):
        module().download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert len(session.calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_load_snapshot_roundtrip_verifies_parquet_hash(tmp_path, monkeypatch):
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    api = module()
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert hasattr(api, "load_snapshot"), "snapshot loading missing"
    frame, loaded = api.load_snapshot(tmp_path, manifest["dataset_id"])
    assert loaded == manifest
    pd.testing.assert_frame_equal(frame, pd.read_parquet(tmp_path / manifest["parquet_path"]))
    with (tmp_path / manifest["parquet_path"]).open("ab") as stream:
        stream.write(b"SYNTHETIC CORRUPTION")
    with pytest.raises(ValueError, match="SHA256"):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


@pytest.mark.parametrize(
    "identifier",
    ["../escape", "..\\escape", "/absolute", "C:\\escape", "", ".", "a" * 32 + "/..", "A" * 32, None],
)
def test_load_rejects_unsafe_dataset_ids(tmp_path, identifier):
    with pytest.raises(ValueError, match="dataset"):
        module().load_snapshot(tmp_path, identifier)


@pytest.mark.parametrize(
    "replacement",
    [
        "../outside.parquet",
        "..\\outside.parquet",
        "/outside.parquet",
        "C:/outside.parquet",
        "file://outside",
        "other/candles.parquet",
        None,
    ],
)
def test_load_rejects_unsafe_manifest_paths(tmp_path, monkeypatch, replacement):
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    api = module()
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    manifest["parquet_path"] = replacement
    (tmp_path / manifest["dataset_id"] / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="path"):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


def test_load_snapshot_verifies_raw_page_hashes(tmp_path, monkeypatch):
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    api = module()
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    (tmp_path / manifest["raw_pages"][0]["path"]).write_bytes(b"SYNTHETIC CORRUPTION")
    with pytest.raises(ValueError, match="SHA256"):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


def test_load_rejects_raw_page_path_traversal(tmp_path, monkeypatch):
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    api = module()
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    manifest["raw_pages"][0]["path"] = "../outside.json"
    (tmp_path / manifest["dataset_id"] / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="path"):
        api.load_snapshot(tmp_path, manifest["dataset_id"])


def test_load_rejects_snapshot_directory_junction_escape(tmp_path, monkeypatch):
    import os
    import subprocess

    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    api = module()
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    directory = tmp_path / manifest["dataset_id"]
    outside = tmp_path / "synthetic-redirect-target"
    directory.rename(outside)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(directory), str(outside)], capture_output=True
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
    else:
        directory.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="path|escape"):
            api.load_snapshot(tmp_path, manifest["dataset_id"])
    finally:
        if os.name == "nt":
            directory.rmdir()
        else:
            directory.unlink()


def test_validate_rejects_nullable_missing_values_as_value_error():
    frame = synthetic_frame().astype("Float64")
    frame.iloc[0, 0] = pd.NA
    with pytest.raises(ValueError, match="missing|finite"):
        module().validate_frame(frame)


@pytest.mark.parametrize(
    "field,value",
    [
        ("dataset_id", "f" * 32),
        ("rows", 42),
        ("rows", True),
        ("source", "https://invalid.example"),
        ("symbol", "ETHUSDT"),
        ("interval", "1m"),
        ("start_ms", START + HOUR),
        ("end_ms", START),
        ("raw_pages", []),
        ("fetched_at", "not a timestamp"),
    ],
)
def test_load_rejects_inconsistent_manifest_metadata(tmp_path, monkeypatch, field, value):
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    api = module()
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    dataset_id = manifest["dataset_id"]
    manifest[field] = value
    (tmp_path / dataset_id / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        api.load_snapshot(tmp_path, dataset_id)


def test_existing_snapshot_is_never_overwritten_on_id_collision(tmp_path, monkeypatch):
    from types import SimpleNamespace

    api = module()
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    originals = {path: path.read_bytes() for path in (tmp_path / manifest["dataset_id"]).iterdir()}
    monkeypatch.setattr(api.uuid, "uuid4", lambda: SimpleNamespace(hex=manifest["dataset_id"]))
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    with pytest.raises(FileExistsError):
        api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert all(path.read_bytes() == content for path, content in originals.items())


def test_repeated_page_fails_instead_of_looping(tmp_path, monkeypatch):
    first = SyntheticResponse([synthetic_kline(i) for i in range(1000)])
    session = install_http(monkeypatch, [first, first])
    with pytest.raises(ValueError, match="timestamps"):
        module().download_snapshot(tmp_path, start_ms=START, end_ms=START + 1001 * HOUR)
    assert len(session.calls) == 2
    assert list(tmp_path.iterdir()) == []


def test_empty_response_cannot_create_a_snapshot(tmp_path, monkeypatch):
    session = install_http(monkeypatch, [SyntheticResponse([])])
    with pytest.raises(ValueError, match="nonempty"):
        module().download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert len(session.calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_http_4xx_is_not_retried(tmp_path, monkeypatch):
    session = install_http(monkeypatch, [SyntheticResponse({}, 400)])
    with pytest.raises(requests.HTTPError):
        module().download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert len(session.calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_manifest_records_the_closed_candle_cutoff_time(tmp_path, monkeypatch):
    api = module()
    fixed_now = START + 2 * HOUR
    monkeypatch.setattr(api, "_now_ms", lambda: fixed_now)
    install_http(monkeypatch, [SyntheticResponse([synthetic_kline(0)])])
    manifest = api.download_snapshot(tmp_path, start_ms=START, end_ms=START + HOUR)
    assert pd.Timestamp(manifest["fetched_at"]).value // 1_000_000 == fixed_now
    api.load_snapshot(tmp_path, manifest["dataset_id"])


def module():
    assert importlib.util.find_spec("trading_lab.data") is not None, "data module missing"
    return importlib.import_module("trading_lab.data")


def synthetic_frame():
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Volume": [1.0, 0.0],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )


def test_validate_accepts_synthetic_hourly_utc_frame():
    assert module().validate_frame(synthetic_frame()) is None


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "nan",
        "infinite",
        "duplicate",
        "gap",
        "naive",
        "nonutc",
        "nat",
        "negative_volume",
        "zero_price",
        "negative_price",
        "ohlc",
        "unsorted",
        "empty",
        "offhour",
    ],
)
def test_validate_rejects_invalid_synthetic_frames(fault):
    frame = synthetic_frame()
    if fault == "missing":
        frame = frame.drop(columns="Volume")
    if fault == "nan":
        frame.iloc[0, 0] = float("nan")
    if fault == "infinite":
        frame.iloc[0, 0] = float("inf")
    if fault == "duplicate":
        frame.index = frame.index[[0, 0]]
    if fault == "gap":
        frame.index = pd.date_range("2024-01-01", periods=2, freq="2h", tz="UTC")
    if fault == "naive":
        frame.index = frame.index.tz_localize(None)
    if fault == "nonutc":
        frame.index = frame.index.tz_convert("Asia/Bangkok")
    if fault == "nat":
        frame.index = pd.DatetimeIndex([frame.index[0], pd.NaT])
    if fault == "negative_volume":
        frame.iloc[0, 4] = -1
    if fault == "zero_price":
        frame.iloc[0, 0] = 0
    if fault == "negative_price":
        frame.iloc[0, 0] = -1
    if fault == "ohlc":
        frame.iloc[0, 1] = 9
    if fault == "unsorted":
        frame = frame.iloc[::-1]
    if fault == "empty":
        frame = frame.iloc[:0]
    if fault == "offhour":
        frame.index = pd.date_range("2024-01-01 00:01", periods=2, freq="h", tz="UTC")
    with pytest.raises(ValueError):
        module().validate_frame(frame)
