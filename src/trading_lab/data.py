"""Public, read-only Binance snapshot ingestion."""
import math
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

import pandas as pd

COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
HOUR_MS = 3_600_000


def validate_frame(frame):
    """Validate nonempty, contiguous, hourly UTC OHLCV; raise ValueError."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("OHLCV frame must be nonempty")
    if not frame.columns.is_unique or any(c not in frame for c in COLUMNS):
        raise ValueError("Missing or duplicate OHLCV columns")
    index = frame.index
    if (not isinstance(index, pd.DatetimeIndex) or str(index.tz) != "UTC"
            or index.hasnans or not index.is_unique or not index.is_monotonic_increasing):
        raise ValueError("Index must be unique, ordered, timezone-aware UTC")
    if not (index == index.floor("h")).all():
        raise ValueError("Timestamps must be hourly aligned")
    if len(index) > 1 and not ((index.as_unit("ms").asi8[1:] - index.as_unit("ms").asi8[:-1]) == HOUR_MS).all():
        raise ValueError("Hourly candles contain gaps")
    if any(not pd.api.types.is_numeric_dtype(frame[c]) or pd.api.types.is_bool_dtype(frame[c])
           or pd.api.types.is_complex_dtype(frame[c]) for c in COLUMNS):
        raise ValueError("OHLCV values must be real numeric, not booleans")
    if frame[COLUMNS].isna().any().any():
        raise ValueError("OHLCV values must be nonmissing")
    if not all(math.isfinite(value) for row in frame[COLUMNS].itertuples(index=False, name=None) for value in row):
        raise ValueError("OHLCV must be finite and nonmissing")
    if (frame[COLUMNS[:4]] <= 0).any().any() or (frame.Volume < 0).any():
        raise ValueError("Prices must be positive and volume nonnegative")
    if ((frame.High < frame[["Open", "Close", "Low"]].max(axis=1)).any()
            or (frame.Low > frame[["Open", "Close", "High"]].min(axis=1)).any()):
        raise ValueError("Inconsistent OHLC prices")


SOURCE = "https://data-api.binance.vision/api/v3/klines"


def _now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _rest_page(payload, cursor, end_ms):
    """Decode the exact archived bytes and enforce the hourly REST contract."""
    page = json.loads(payload)
    if not isinstance(page, list) or len(page) > 1000:
        raise ValueError("REST klines must be a list of at most 1000 rows")
    previous = cursor - 1
    for row in page:
        if not isinstance(row, list) or len(row) != 12:
            raise ValueError("Malformed REST kline row")
        opened, closed = row[0], row[6]
        if (type(opened) is not int or type(closed) is not int
                or not cursor <= opened < end_ms or opened <= previous
                or opened % HOUR_MS != 0 or closed != opened + HOUR_MS - 1):
            raise ValueError("REST timestamps must be ordered hourly Unix milliseconds")
        previous = opened
        try:
            if any(type(v) not in (str, int, float) for v in row[1:6]):
                raise ValueError("Invalid REST OHLCV value type")
            opened_price, high, low, close, volume = [float(v) for v in row[1:6]]
        except (TypeError, OverflowError) as exc:
            raise ValueError("Malformed REST OHLCV values") from exc
        if (not all(math.isfinite(v) for v in (opened_price, high, low, close, volume))
                or min(opened_price, high, low, close) <= 0 or volume < 0
                or high < max(opened_price, low, close) or low > min(opened_price, high, close)):
            raise ValueError("Invalid REST OHLCV values")
    return page


def _closed_frame(rows, start_ms, end_ms, fetched_ms):
    rows = [row for row in rows if start_ms <= row[0] < end_ms
            and row[6] < min(end_ms, fetched_ms)]
    frame = pd.DataFrame([[float(v) for v in row[1:6]] for row in rows], columns=COLUMNS,
                         index=pd.to_datetime([row[0] for row in rows], unit="ms", utc=True))
    frame.index.name = "Date"
    validate_frame(frame)
    expected_first = ((start_ms + HOUR_MS - 1) // HOUR_MS) * HOUR_MS
    expected_last = ((min(end_ms, fetched_ms) // HOUR_MS) - 1) * HOUR_MS
    stamps = frame.index.as_unit("ms").asi8
    if stamps[0] != expected_first or stamps[-1] != expected_last:
        raise ValueError("snapshot coverage is incomplete at requested boundaries")
    return frame


def download_snapshot(root, symbol="BTCUSDT", interval="1h", *, start_ms: int, end_ms: int) -> dict:
    """Save a new snapshot of hourly candles in [start_ms, end_ms)."""
    if symbol != "BTCUSDT" or interval != "1h":
        raise ValueError("Only BTCUSDT 1h public candles are supported")
    if (type(start_ms) is not int or type(end_ms) is not int
            or not 0 <= start_ms < end_ms <= 9_223_372_036_854):
        raise ValueError("start_ms/end_ms must be ordered integer Unix milliseconds")
    if end_ms - start_ms > 3 * 366 * 24 * HOUR_MS:
        raise ValueError('ingestion budget: maximum three years per snapshot')
    pages, rows = [], []
    fetched_ms = _now_ms()
    cursor = start_ms
    session = requests.Session()
    session.trust_env = False
    session.auth = None
    try:
        while cursor < end_ms:
            for attempt in range(3):
                try:
                    response = session.get(
                        SOURCE, params={"symbol": symbol, "interval": interval,
                                        "startTime": cursor, "endTime": end_ms - 1, "limit": 1000},
                        timeout=(5, 30), allow_redirects=False,
                    )
                except (requests.Timeout, requests.ConnectionError):
                    if attempt == 2:
                        raise
                    time.sleep(0.5 * 2 ** attempt)
                    continue
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    if attempt < 2:
                        time.sleep(0.5 * 2 ** attempt)
                        continue
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError("Unexpected HTTP status; redirects are forbidden")
                break
            page = _rest_page(response.content, cursor, end_ms)
            pages.append(response.content)
            if not page:
                break
            rows.extend(row for row in page if start_ms <= row[0] < end_ms
                        and row[6] < min(end_ms, fetched_ms))
            cursor = page[-1][0] + HOUR_MS
    finally:
        session.close()
    frame = _closed_frame(rows, start_ms, end_ms, fetched_ms)
    root = Path(root)
    dataset_id = uuid.uuid4().hex
    directory = root / dataset_id
    directory.mkdir(parents=True, exist_ok=False)
    raw_pages = []
    for number, payload in enumerate(pages):
        relative = f"{dataset_id}/raw-{number:05d}.json"
        with (root / relative).open("xb") as stream:
            stream.write(payload)
        raw_pages.append({"path": relative, "sha256": hashlib.sha256(payload).hexdigest()})
    relative = f"{dataset_id}/candles.parquet"
    with (root / relative).open("xb") as stream:
        frame.to_parquet(stream, engine="pyarrow")
    manifest = {"dataset_id": dataset_id, "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest(),
                "parquet_path": relative, "rows": len(frame), "source": SOURCE,
                "symbol": symbol, "interval": interval, "start_ms": start_ms, "end_ms": end_ms,
                "fetched_at": datetime.fromtimestamp(fetched_ms / 1000, timezone.utc).isoformat(),
                "raw_pages": raw_pages}
    manifest["dataset_sha256"] = _dataset_sha256(manifest)
    with (directory / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    return manifest


def _safe_file(root, dataset_id, filename):
    root = Path(root).resolve()
    directory = root / dataset_id
    path = directory / filename
    if directory.resolve() != directory or path.resolve().parent != directory:
        raise ValueError("Snapshot path escapes its immutable directory")
    return path


def _dataset_sha256(manifest):
    """Bind every manifest field (including verified file digests), except identity itself."""
    canonical = {key: value for key, value in manifest.items() if key != "dataset_sha256"}
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_snapshot(root, dataset_id):
    """Verify raw/Parquet correspondence and return a provenance-bound dataset identity.

    ``sha256`` remains the Parquet hash. Legacy manifests derive ``dataset_sha256``
    in memory only; a persisted identity must match the canonical manifest hash.
    """
    if not isinstance(dataset_id, str) or re.fullmatch(r"[0-9a-f]{32}", dataset_id) is None:
        raise ValueError("Unsafe dataset_id")
    root = Path(root)
    manifest_path = _safe_file(root, dataset_id, "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"dataset_id", "sha256", "parquet_path", "rows", "source", "symbol", "interval",
                "start_ms", "end_ms", "fetched_at", "raw_pages"}
    if not isinstance(manifest, dict) or not required.issubset(manifest):
        raise ValueError("Incomplete snapshot manifest")
    if (manifest["dataset_id"] != dataset_id or manifest["source"] != SOURCE
            or manifest["symbol"] != "BTCUSDT" or manifest["interval"] != "1h"
            or type(manifest["rows"]) is not int or manifest["rows"] <= 0
            or type(manifest["start_ms"]) is not int or type(manifest["end_ms"]) is not int
            or not 0 <= manifest["start_ms"] < manifest["end_ms"] <= 9_223_372_036_854
            or not isinstance(manifest["raw_pages"], list) or not manifest["raw_pages"]):
        raise ValueError("Inconsistent snapshot manifest metadata")
    fetched_at = pd.Timestamp(manifest["fetched_at"])
    if pd.isna(fetched_at) or str(fetched_at.tz) != "UTC":
        raise ValueError("Manifest fetch time must be UTC")
    if manifest.get("parquet_path") != f"{dataset_id}/candles.parquet":
        raise ValueError("Unsafe Parquet path in manifest")
    path = _safe_file(root, dataset_id, "candles.parquet")
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("Parquet SHA256 mismatch")
    rows = []
    cursor = manifest["start_ms"]
    finished = False
    for number, raw in enumerate(manifest["raw_pages"]):
        if finished or cursor >= manifest["end_ms"]:
            raise ValueError("Unexpected raw page after REST pagination ended")
        if not isinstance(raw, dict) or raw.get("path") != f"{dataset_id}/raw-{number:05d}.json":
            raise ValueError("Unsafe raw page path in manifest")
        raw_path = _safe_file(root, dataset_id, f"raw-{number:05d}.json")
        payload = raw_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != raw.get("sha256"):
            raise ValueError("Raw page SHA256 mismatch")
        page = _rest_page(payload, cursor, manifest["end_ms"])
        rows.extend(page)
        if page:
            cursor = page[-1][0] + HOUR_MS
        else:
            finished = True
    reconstructed = _closed_frame(
        rows, manifest["start_ms"], manifest["end_ms"], fetched_at.value // 1_000_000,
    )
    frame = pd.read_parquet(path, engine="pyarrow")
    validate_frame(frame)
    try:
        pd.testing.assert_frame_equal(frame, reconstructed, check_exact=True, check_freq=False)
    except AssertionError as exc:
        raise ValueError("Raw pages do not correspond exactly to Parquet") from exc
    stamps = frame.index.as_unit("ms").asi8
    if (len(frame) != manifest["rows"] or stamps[0] < manifest["start_ms"]
            or stamps[-1] + HOUR_MS > min(manifest["end_ms"], fetched_at.value // 1_000_000)):
        raise ValueError("Snapshot rows or time bounds disagree with manifest")
    identity = _dataset_sha256(manifest)
    if "dataset_sha256" in manifest and manifest["dataset_sha256"] != identity:
        raise ValueError("Dataset SHA256 mismatch")
    manifest["dataset_sha256"] = identity
    return frame, manifest
